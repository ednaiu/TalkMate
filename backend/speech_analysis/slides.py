"""Чтение презентации: что написано на каждом слайде.

Слайд читается двумя способами. Из текстового слоя PDF берутся надписи, набранные текстом. Затем страница
отрисовывается в картинку, и модель распознавания текста (PP-OCRv5 для восточнославянских языков, запуск
через onnxruntime) находит на ней строки вместе с их положением и высотой. Второй способ нужен для того,
чего в текстовом слое нет: надписей внутри схем, снимков экрана и слайдов, сохранённых картинками. Он же
даёт размер шрифта, по которому видно, читается ли слайд из зала.
"""
import logging
from dataclasses import dataclass, field

from . import lang
from .speed import tokenize

log = logging.getLogger(__name__)

MAX_PAGES = 40            # больше слайдов в учебном выступлении не бывает, а разбор длинного файла идёт минуты
RENDER_WIDTH = 1280       # ширина картинки слайда для распознавания
MIN_SCORE = 0.8           # строки, в которых модель не уверена, чаще оказываются логотипами и значками
SMALL_LINE_SHARE = 0.025  # строка ниже 2,5% высоты слайда: шрифт мельче 11 пунктов на обычном слайде


class SlidesError(ValueError):
    """Файл презентации не удалось прочитать."""


@dataclass
class Slide:
    page: int
    text: str = ""
    title: str = ""
    words: int = 0
    small_text: float = 0.0     # доля текста, набранного слишком мелко
    from_image: float = 0.0     # доля слов, которых нет в текстовом слое: они нарисованы на картинке

    @property
    def typed_words(self):
        """Слова, набранные текстом: надписи внутри схем и снимков экрана в перегруженность не идут."""
        return round(self.words * (1 - self.from_image))
    lines: list = field(default_factory=list)


def first_line(text):
    for line in (text or "").splitlines():
        if len(tokenize(line)) >= 1 and len(line.strip()) > 2:
            return line.strip()
    return ""


def merge(layer_text, lines, page_height):
    """Соединяет текстовый слой с распознанными строками. lines: [(текст, уверенность, верх, низ)]."""
    layer_words = set(tokenize(layer_text))
    extra, sizes = [], []
    title, title_height = "", 0.0
    for text, score, top, bottom in lines:
        if score < MIN_SCORE:
            continue
        words = tokenize(text)
        if not words:
            continue
        height = bottom - top
        sizes.append((len(text), height / page_height if page_height else 0.0))
        # Если текстового слоя нет, заголовком считаем самую крупную строку в верхней половине слайда.
        if top < page_height * 0.5 and height > title_height and sum(len(w) for w in words) >= 3:
            title, title_height = text.strip(), height
        new = [w for w in words if w not in layer_words]
        # Строку добавляем, только если в ней есть слова, которых нет в слое, иначе текст задвоится.
        if new and len(new) * 2 >= len(words):
            extra.append(text.strip())
    text = "\n".join(part for part in [layer_text.strip(), "\n".join(extra)] if part)
    total = len(tokenize(text))
    chars = sum(size for size, _ in sizes)
    small = sum(size for size, share in sizes if share < SMALL_LINE_SHARE) / chars if chars else 0.0
    from_image = len(tokenize("\n".join(extra))) / total if total else 0.0
    return Slide(page=0, text=text, title=first_line(layer_text) or title, words=total,
                 small_text=round(small, 2), from_image=round(from_image, 2))


class SlideReader:
    """Читает PDF: текстовый слой через pdfium, картинку слайда через модель распознавания текста."""

    def __init__(self, ocr=True):
        self.use_ocr = ocr
        self._engines = {}

    def _ocr(self):
        # У английской речи слайды английские: для них берётся модель латиницы, она не путает буквы с кириллицей.
        language = lang.speech()
        if language not in self._engines and self.use_ocr:
            try:
                from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR

                script = LangRec.EN if language == "en" else LangRec.ESLAV
                self._engines[language] = RapidOCR(params={"Rec.lang_type": script, "Rec.ocr_version": OCRVersion.PPOCRV5,
                                                           "Rec.model_type": ModelType.MOBILE, "Global.log_level": "error"})
            except Exception:
                log.exception("Модель распознавания текста недоступна, слайды читаются только по текстовому слою")
                self.use_ocr = False
        return self._engines.get(language)

    def recognize(self, image):
        """Строки на картинке слайда: [(текст, уверенность, верх, низ)]."""
        engine = self._ocr()
        if engine is None:
            return []
        import numpy as np

        result = engine(np.array(image))
        if result is None or not result.txts:
            return []
        return [(text, float(score), float(min(p[1] for p in box)), float(max(p[1] for p in box)))
                for text, score, box in zip(result.txts, result.scores, result.boxes)]

    def read(self, path):
        try:
            import pypdfium2 as pdfium

            document = pdfium.PdfDocument(str(path))
            count = len(document)
        except Exception as exc:
            raise SlidesError(lang.text("Не удалось прочитать презентацию: нужен файл PDF",
                                        "Could not read the presentation: a PDF file is required")) from exc
        if count == 0:
            raise SlidesError(lang.text("В презентации нет слайдов", "The presentation has no slides"))
        slides = []
        for index in range(min(count, MAX_PAGES)):
            page = document[index]
            width, height = page.get_size()
            try:
                layer = page.get_textpage().get_text_bounded() or ""
            except Exception:
                layer = ""
            lines, pixel_height = [], height
            if self.use_ocr:
                image = page.render(scale=RENDER_WIDTH / width).to_pil()
                pixel_height = image.height
                try:
                    lines = self.recognize(image)
                except Exception:
                    log.exception("Не удалось распознать слайд %s", index + 1)
            slide = merge(layer, lines, pixel_height)
            slide.page = index + 1
            slides.append(slide)
        return slides


class StubSlideReader:
    """Для тестов: отдаёт заранее заданные тексты слайдов."""

    def __init__(self, texts):
        self.texts = texts

    def read(self, path):
        return [Slide(page=i + 1, text=text, title=first_line(text), words=len(tokenize(text))) for i, text in enumerate(self.texts)]


def make_slide_reader(config):
    return SlideReader(ocr=getattr(config, "SLIDES_OCR", "on") != "off")
