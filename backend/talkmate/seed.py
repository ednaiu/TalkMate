"""Начальные данные: администратор, пороги и статьи с экрана «Статьи»."""
from speech_analysis.thresholds import DEFAULT_THRESHOLDS, PREVIOUS_DEFAULTS

from .models import Article, User
from .repositories import ArticleRepository, ThresholdRepository, UserRepository
from .services.auth_service import hash_password

ARTICLES = [
    (
        "Жестикуляция и движение",
        "Жестикуляция, которой пользуются американские актёры, обученные по системе Михаила Чехова "
        "(от Энтони Хопкинса до Джонни Деппа), состоит из пяти основных жестов: **толкание, вытягивание, "
        "подъём, бросание и разрывание.** Каждое из них можно выполнить в шести направлениях: вверх, вниз, "
        "влево, вправо, вперёд или назад, и бесконечно варьировать по интенсивности. Этот набор позволяет "
        "выразить шесть мотивов, которые движут персонажем: «я хочу», «я отвергаю», «я даю», «я беру», "
        "«я удерживаю» и «я уступаю».\n\n"
        "На выступлении жест работает, когда он появляется чуть раньше слова. Сначала рука, потом фраза: "
        "так слушатель успевает увидеть мысль до того, как её услышит.\n\n"
        "**Что делать с руками.** Держите их на уровне между поясом и грудью, ладони открыты. Руки в карманах "
        "и скрещённые на груди читаются как закрытость. Если не знаете, куда их деть, соедините кончики "
        "пальцев перед собой.\n\n"
        "**Как двигаться.** Шаг делайте на смене мысли и стойте на месте, пока её договариваете. "
        "Хождение из стороны в сторону без причины выдаёт волнение и отвлекает от слов."
    ),
    (
        "Подготовка на площадке",
        "Приходите в зал за полчаса до начала. За это время нужно успеть пройти от двери до места, откуда "
        "будете говорить, встать там и сказать вслух первые две фразы.\n\n"
        "**Проверьте технику сами.** Микрофон, кликер, переходник для ноутбука, звук в видео. "
        "Половина сорванных начал случается из-за кабеля, который не подошёл.\n\n"
        "**Послушайте зал.** Попросите кого-нибудь сесть в последний ряд и сказать, слышно ли вас без "
        "микрофона. В гулком помещении говорите медленнее, чем привыкли, иначе слова сольются.\n\n"
        "**Найдите свои точки.** Выберите трёх людей в разных частях зала и переводите взгляд между ними. "
        "Остальным будет казаться, что вы смотрите на каждого.\n\n"
        "Воду поставьте заранее и откройте бутылку. Глоток воды посреди выступления выглядит как "
        "спокойная пауза, а борьба с крышкой нет."
    ),
    (
        "Использование презентаций",
        "Слайды нужны слушателям, а не докладчику. Если вы читаете текст с экрана, зал читает его быстрее "
        "вас и перестаёт слушать.\n\n"
        "**Одна мысль на слайд.** Заголовок формулируйте как вывод: «Продажи выросли на треть», а не "
        "«Динамика продаж». Тогда слайд понятен и тем, кто отвлёкся.\n\n"
        "**Меньше текста.** Шрифт не мельче 24 пунктов, не больше шести строк. Таблицу на сорок ячеек "
        "замените графиком и одной цифрой, ради которой её показывали.\n\n"
        "**Сначала скажите, потом покажите.** Переключайте слайд после того, как подвели к нему словами. "
        "Иначе внимание уйдёт на экран раньше, чем вы начали объяснять.\n\n"
        "Держите запасной план: файл в PDF на флешке и готовность рассказать всё без проектора. "
        "Хорошее выступление переживает сломанную технику."
    ),
    (
        "Разогрев",
        "Голос работает как мышца, и перед нагрузкой его разминают. Хватит пяти минут в коридоре.\n\n"
        "**Дыхание.** Вдох носом на четыре счёта, выдох ртом на восемь. Пять повторов снижают пульс "
        "и убирают дрожь в голосе.\n\n"
        "**Лицо и челюсть.** Широко зевните несколько раз, подвигайте челюстью, надуйте и сдуйте щёки. "
        "Зажатая челюсть делает речь невнятной.\n\n"
        "**Звук.** Помычите с закрытым ртом, скользя от низкой ноты к высокой и обратно. "
        "Затем проговорите пару скороговорок, медленно и с преувеличенной артикуляцией.\n\n"
        "**Первая фраза.** Произнесите её вслух три раза с разной интонацией. Когда начало выучено "
        "голосом, а не глазами, первые секунды на сцене проходят спокойнее."
    ),
    (
        "Слова-заполнители",
        "«Ну», «вот», «как бы», «короче» появляются, когда мысль ещё не готова, а молчать страшно. "
        "Слушатель замечает их быстрее, чем кажется говорящему.\n\n"
        "**Замените слово паузой.** Секунда тишины звучит увереннее любого «э-э». Пауза кажется "
        "длинной только тому, кто говорит.\n\n"
        "**Узнайте свои слова.** Запишите выступление в разделе «Тренировка» и посмотрите результат: "
        "приложение покажет, какие заполнители вы используете чаще всего.\n\n"
        "**Говорите короче.** Заполнители живут на стыках длинных предложений. Точка вместо «и вот» "
        "убирает половину из них."
    ),
]


ARTICLES_EN = [
    (
        "Gestures and movement",
        "The gestures used by American actors trained in the Michael Chekhov technique (from Anthony Hopkins to Johnny Depp) "
        "come down to five basic ones: **pushing, pulling, lifting, throwing and tearing.** Each can go in six directions: "
        "up, down, left, right, forward or back, and vary endlessly in intensity. This set expresses the six motives that "
        "drive a character: “I want”, “I reject”, “I give”, “I take”, “I hold” and “I yield”.\n\n"
        "In a talk a gesture works when it comes slightly before the word. First the hand, then the phrase: "
        "the listener sees the idea before hearing it.\n\n"
        "**What to do with your hands.** Keep them between waist and chest, palms open. Hands in pockets "
        "or crossed on the chest read as being closed off. If you do not know where to put them, join your "
        "fingertips in front of you.\n\n"
        "**How to move.** Take a step when the idea changes and stand still while you finish it. "
        "Pacing from side to side for no reason shows nerves and distracts from the words."
    ),
    (
        "Preparing on site",
        "Come to the room half an hour early. In that time walk from the door to the spot you will speak from, "
        "stand there and say your first two sentences aloud.\n\n"
        "**Check the equipment yourself.** Microphone, clicker, laptop adapter, sound in the video. "
        "Half of all ruined openings come from a cable that did not fit.\n\n"
        "**Listen to the room.** Ask someone to sit in the last row and tell you whether you can be heard without "
        "a microphone. In an echoing room speak more slowly than usual, or the words will blur.\n\n"
        "**Find your points.** Pick three people in different parts of the room and move your gaze between them. "
        "Everyone else will feel that you are looking at them.\n\n"
        "Put the water out in advance and open the bottle. A sip of water mid-talk looks like "
        "a calm pause, a fight with the cap does not."
    ),
    (
        "Using slides",
        "Slides are for the audience, not for the speaker. If you read text off the screen, the room reads it faster "
        "than you and stops listening.\n\n"
        "**One idea per slide.** Word the title as a conclusion: “Sales grew by a third”, not "
        "“Sales dynamics”. Then the slide makes sense even to those who drifted off.\n\n"
        "**Less text.** No font smaller than 24 points, no more than six lines. Replace a forty-cell table "
        "with a chart and the one number it was shown for.\n\n"
        "**Say it first, then show it.** Switch the slide after you have led up to it in words. "
        "Otherwise attention goes to the screen before you start explaining.\n\n"
        "Keep a backup plan: the file as a PDF on a flash drive and the readiness to tell it all without a projector. "
        "A good talk survives broken equipment."
    ),
    (
        "Warm-up",
        "The voice works like a muscle and needs warming up before a load. Five minutes in the corridor is enough.\n\n"
        "**Breathing.** Breathe in through the nose for four counts, out through the mouth for eight. Five rounds lower "
        "the pulse and take the tremor out of the voice.\n\n"
        "**Face and jaw.** Yawn widely a few times, move your jaw, puff your cheeks out and in. "
        "A tight jaw makes speech unclear.\n\n"
        "**Sound.** Hum with your mouth closed, sliding from a low note to a high one and back. "
        "Then say a couple of tongue twisters, slowly and with exaggerated articulation.\n\n"
        "**The first sentence.** Say it aloud three times with different intonation. When the opening is learned "
        "by voice and not by eye, the first seconds on stage go more calmly."
    ),
    (
        "Filler words",
        "“Um”, “like”, “you know” and “basically” appear when the thought is not ready yet and silence feels scary. "
        "The listener notices them sooner than the speaker thinks.\n\n"
        "**Replace the word with a pause.** A second of silence sounds more confident than any “uh”. The pause feels "
        "long only to the one speaking.\n\n"
        "**Learn your own words.** Record a talk in the Practice section and look at the result: "
        "the app shows which fillers you use most.\n\n"
        "**Speak in shorter sentences.** Fillers live at the joints of long sentences. A full stop instead of “and so” "
        "removes half of them."
    ),
]


def seed(session, config):
    thresholds = ThresholdRepository(session)
    stored = thresholds.stored()
    for key, value in DEFAULT_THRESHOLDS.items():
        if key not in stored:
            thresholds.set(key, value)
    for previous in PREVIOUS_DEFAULTS:
        if all(stored.get(key) == old for key, old in previous.items()):
            for key in previous:
                thresholds.set(key, DEFAULT_THRESHOLDS[key])

    articles = ArticleRepository(session)
    if articles.is_empty():
        for title, content in ARTICLES:
            articles.add(Article(title=title, content=content, lang="ru"))
    # Английские статьи добавляются и в базу, созданную до появления английской версии.
    if not articles.has_language("en"):
        for title, content in ARTICLES_EN:
            articles.add(Article(title=title, content=content, lang="en"))

    users = UserRepository(session)
    email = config.ADMIN_EMAIL.strip().lower()
    if email and users.by_email(email) is None:
        users.add(User(name=config.ADMIN_NAME, email=email, password=hash_password(config.ADMIN_PASSWORD), role="admin"))
    session.commit()
