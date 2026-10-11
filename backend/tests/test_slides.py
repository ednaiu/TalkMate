"""Презентация: чтение PDF и сопоставление слайдов с речью."""
import io

import pytest

from speech_analysis.embeddings import StubEmbedder
from speech_analysis.server import parse_slide_times
from speech_analysis.slide_match import align, match_slides, reading_share
from speech_analysis.slides import Slide, SlideReader, SlidesError, StubSlideReader, merge

SLIDES = [
    "Актуальность темы\nСтрах публичных выступлений мешает студентам на защите диплома",
    "Архитектура приложения\nМобильный клиент отправляет запись на сервер анализа",
    "Результаты эксперимента\nПосле недели тренировок участники снизили количество заполнителей",
]


def segment(start, end, text):
    return {"start": start, "end": end, "text": text}


def make_pdf(pages):
    """Минимальный PDF с латинским текстом: по строке на страницу."""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for text in pages:
        stream = f"BT /F1 24 Tf 72 300 Td ({text}) Tj ET"
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 720 405] /Contents {len(objects)} 0 R "
                       "/Resources << /Font << /F1 3 0 R >> >> >>")
        kids.append(f"{len(objects)} 0 R")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    out, offsets = io.BytesIO(), []
    out.write(b"%PDF-1.4\n")
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1"))
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return out.getvalue()


def test_text_layer_is_read_page_by_page(tmp_path):
    path = tmp_path / "deck.pdf"
    path.write_bytes(make_pdf(["Speech rate and pauses", "Emotion model training"]))
    slides = SlideReader(ocr=False).read(path)
    assert [slide.page for slide in slides] == [1, 2]
    assert "Speech rate" in slides[0].text and slides[0].words == 4
    assert slides[1].title == "Emotion model training"


def test_broken_file_is_reported(tmp_path):
    path = tmp_path / "deck.pdf"
    path.write_bytes(b"this is not a pdf")
    with pytest.raises(SlidesError):
        SlideReader(ocr=False).read(path)


def test_recognized_lines_add_only_what_the_text_layer_lacks():
    lines = [("Архитектура приложения", 0.99, 40, 90), ("Сервер анализа", 0.95, 300, 312), ("V1TM0", 0.4, 10, 80)]
    slide = merge("Архитектура приложения", lines, 720)
    assert slide.title == "Архитектура приложения"
    assert slide.text.count("Архитектура") == 1 and "Сервер анализа" in slide.text
    assert "V1TM0" not in slide.text                       # строка, в которой модель не уверена
    assert slide.from_image == 0.5                         # два слова из четырёх есть только на картинке
    assert 0 < slide.small_text < 1                        # мелкая строка одна из двух


def test_phrases_follow_slides_in_order():
    segments = [
        segment(0, 10, "Многие студенты испытывают страх перед защитой диплома."),
        segment(10, 20, "Клиент шлёт запись, а анализ идёт на сервере."),
        segment(20, 30, "За неделю тренировок участники стали реже говорить заполнители."),
    ]
    result = match_slides(StubSlideReader(SLIDES).read(None), segments, 30)
    assert [item["seconds"] for item in result["items"]] == [10, 10, 10]
    assert all(item["status"] in ("covered", "partly") for item in result["items"])
    assert result["coverage"] >= 40 and result["reading"] == 0


def test_silent_slide_is_marked_as_skipped():
    segments = [
        segment(0, 15, "Многие студенты испытывают страх перед защитой диплома и публичных выступлений."),
        segment(15, 30, "За неделю тренировок участники эксперимента стали реже говорить заполнители."),
    ]
    result = match_slides(StubSlideReader(SLIDES).read(None), segments, 30)
    middle = result["items"][1]
    assert middle["status"] == "skipped" and middle["seconds"] == 0
    assert "сервер" in middle["missed"] or "архитектура" in middle["missed"]
    assert any("Слайд 2" in note for note in result["notes"])


def test_reading_from_the_slide_is_detected():
    text = "Страх публичных выступлений мешает студентам на защите диплома"
    assert reading_share(text, SLIDES[0]) == 100
    assert reading_share("Многие боятся выступать перед комиссией на защите", SLIDES[0]) == 0
    result = match_slides(StubSlideReader(SLIDES[:1]).read(None), [segment(0, 8, text)], 8)
    assert result["reading"] == 100
    assert any("читали" in note for note in result["notes"])


def test_dense_and_small_slides_get_notes():
    wordy = Slide(page=1, text=" ".join(f"слово{i}" for i in range(60)), words=60, small_text=0.8)
    result = match_slides([wordy], [segment(0, 5, "слово1 слово2 слово3 слово4 слово5")], 5)
    item = result["items"][0]
    assert item["dense"] and item["small_text"]
    assert any("Сократите" in note for note in result["notes"]) and any("шрифт" in note for note in result["notes"])


def test_unrelated_speech_gets_a_single_note():
    segments = [segment(0, 10, "Вчера мы ездили на дачу и собирали яблоки."), segment(10, 20, "Погода была прекрасная.")]
    result = match_slides(StubSlideReader(SLIDES).read(None), segments, 20)
    assert result["coverage"] < 10
    assert result["notes"] == ["Речь почти не пересекается с презентацией. **Проверьте, тот ли файл вы приложили.**"]


def test_alignment_never_goes_back():
    similarity = [[0, 0, 5], [5, 0, 0], [0, 0, 5]]
    path = align(similarity, [0.1, 0.5, 0.9], 3)
    assert path == sorted(path)


def test_api_accepts_slides_and_keeps_the_comparison(client, user, make_wav):
    deck = make_pdf(["Project overview for colleagues", "Results and conclusions"])
    with open(make_wav(), "rb") as audio:
        response = client.post("/api/speeches", headers=user["headers"], content_type="multipart/form-data",
                               data={"audio": (audio, "speech.wav"), "slides": (io.BytesIO(deck), "deck.pdf")})
    assert response.status_code == 201, response.get_json()
    created = response.get_json()
    assert created["slides"]["pages"] == 2 and len(created["slides"]["items"]) == 2
    again = client.get(f"/api/speeches/{created['id']}", headers=user["headers"]).get_json()
    assert again["slides"] == created["slides"]


def test_api_without_slides_returns_none_and_rejects_other_formats(client, user, make_wav):
    with open(make_wav(), "rb") as audio:
        plain = client.post("/api/speeches", headers=user["headers"], content_type="multipart/form-data", data={"audio": (audio, "speech.wav")})
    assert plain.get_json()["slides"] is None
    with open(make_wav(), "rb") as audio:
        wrong = client.post("/api/speeches", headers=user["headers"], content_type="multipart/form-data",
                            data={"audio": (audio, "speech.wav"), "slides": (io.BytesIO(b"x"), "deck.pptx")})
    assert wrong.status_code == 400 and wrong.get_json()["error"] == "bad_slides_format"


def test_broken_slides_do_not_break_speech_analysis(client, user, make_wav):
    with open(make_wav(), "rb") as audio:
        response = client.post("/api/speeches", headers=user["headers"], content_type="multipart/form-data",
                               data={"audio": (audio, "speech.wav"), "slides": (io.BytesIO(b"not a pdf"), "deck.pdf")})
    assert response.status_code == 201
    assert "error" in response.get_json()["slides"]


def test_app_marks_give_exact_time_and_override_guessing():
    segments = [
        segment(0, 10, "Многие студенты испытывают страх перед защитой диплома."),
        segment(10, 20, "За неделю тренировок участники стали реже говорить заполнители."),
    ]
    # Докладчик держал первый слайд четыре секунды, второй показал молча, остальное время говорил на третьем.
    marks = [{"page": 1, "start": 0}, {"page": 2, "start": 4}, {"page": 3, "start": 6}]
    result = match_slides(StubSlideReader(SLIDES).read(None), segments, 20, marks)
    assert result["timed"] is True
    assert [item["seconds"] for item in result["items"]] == [4, 2, 14]
    assert result["items"][1]["status"] == "skipped"
    assert result["items"][2]["status"] in ("covered", "partly")
    assert match_slides(StubSlideReader(SLIDES).read(None), segments, 20)["timed"] is False


def test_returning_to_a_slide_adds_up_its_time():
    marks = [{"page": 1, "start": 0}, {"page": 2, "start": 5}, {"page": 1, "start": 8}]
    result = match_slides(StubSlideReader(SLIDES).read(None), [segment(0, 12, "Страх выступлений мешает студентам.")], 12, marks)
    assert [item["seconds"] for item in result["items"]] == [9, 3, 0]


def test_slide_retold_in_other_words_is_not_marked_as_skipped():
    slides = StubSlideReader(["Рост выручки\nПрибыль компании увеличилась вдвое", "Архитектура\nСервер анализа и мобильный клиент",
                              "Планы\nВыход на новые рынки"]).read(None)
    segments = [segment(0, 10, "Доходы фирмы стали больше в два раза.")]
    marks = [{"page": 1, "start": 0}]
    assert match_slides(slides, segments, 10, marks)["items"][0]["status"] == "skipped"
    axes = {"рост": 0, "выручки": 0, "прибыль": 0, "компании": 0, "увеличилась": 0, "вдвое": 0, "доходы": 0, "фирмы": 0, "больше": 0,
            "архитектура": 1, "сервер": 1, "анализа": 1, "клиент": 1, "планы": 2, "рынки": 2}
    retold = match_slides(slides, segments, 10, marks, StubEmbedder(axes))["items"][0]
    assert retold["status"] == "retold" and retold["missed"] == []


def test_slide_marks_are_validated():
    assert parse_slide_times('[{"page": 2, "start": 3.5}]') == [{"page": 2, "start": 3.5}]
    for broken in ("", None, "oops", '[{"page": 0, "start": 1}]', '[{"page": 1}]', '[{"page": 1, "start": -2}]', "[]"):
        assert parse_slide_times(broken) is None


def test_api_passes_slide_marks_to_the_comparison(client, user, make_wav):
    deck = make_pdf(["Project overview for colleagues", "Results and conclusions"])
    with open(make_wav(), "rb") as audio:
        response = client.post("/api/speeches", headers=user["headers"], content_type="multipart/form-data",
                               data={"audio": (audio, "speech.wav"), "slides": (io.BytesIO(deck), "deck.pdf"),
                                     "slide_times": '[{"page": 1, "start": 0}, {"page": 2, "start": 1}]'})
    report = response.get_json()["slides"]
    assert report["timed"] is True and [item["seconds"] for item in report["items"]] == [1, 3]
