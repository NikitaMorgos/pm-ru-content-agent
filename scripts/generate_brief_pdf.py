"""Generate a PDF briefing for Nika: updated project description + questions for tomorrow."""

from __future__ import annotations

import sys
from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "docs" / "PM-RU_Brief_for_Nika_call_21_april.pdf"

_FONT_CANDIDATES = [
    Path(r"C:\Windows\Fonts\arial.ttf"),
    Path(r"C:\Windows\Fonts\Arial.ttf"),
    Path(r"C:\Windows\Fonts\segoeui.ttf"),
    Path(r"C:\Windows\Fonts\calibri.ttf"),
]


def _pick_font() -> Path:
    for p in _FONT_CANDIDATES:
        if p.is_file():
            return p
    msg = (
        "Не найден подходящий TTF-шрифт с кириллицей. "
        "Укажите путь к .ttf в переменной окружения CONTENT_AGENT_PDF_FONT."
    )
    raise FileNotFoundError(msg)


def _font_path() -> Path:
    env = __import__("os").environ.get("CONTENT_AGENT_PDF_FONT")
    if env:
        p = Path(env)
        if p.is_file():
            return p
    return _pick_font()


# ─── Slide content ────────────────────────────────────────────────────────────
# Each item: (title, subtitle_or_None, [(bullet_text, is_subitem), ...])
# is_subitem=True → indented smaller bullet

SLIDES: list[tuple[str, str | None, list[tuple[str, bool]]]] = [
    (
        "Созвон 21 апреля 2026",
        "PM-RU Content Agent — уточнение брифа",
        [
            ("Итоги созвона 20 апреля + анализ примеров задач из Redmine", False),
            ("Открытые вопросы для согласования перед стартом разработки", False),
        ],
    ),
    (
        "Что уже зафиксировали (итоги 20 апреля)",
        None,
        [
            ("MVP: одна задача = один артикул — подтверждено", False),
            ("Пилотные категории: ОПМ Кухня — стулья + обеденные столы", False),
            ("Следующий этап после пилота: мягкая мебель", False),
            ("Объём пилота: 10–20 задач → критерий готовности к следующей категории", False),
            ("Размерные схемы — откладываем, нужен отдельный агент", False),
            ("Примерное соотношение: 1 артикул ≈ 6–7 вариантов (цвет/размер)", False),
        ],
    ),
    (
        "Что нашли в примерах задач (Redmine)",
        "Стул Феликс #229405 и Стол Бенни ЛДСП #230073",
        [
            ("Стул: 1 артикул, 8 вариантов (ID), 48 изображений на выходе", False),
            ("Стол: 2 артикула, 16 вариантов, 128 изображений — задача уже содержит несколько артикулов", False),
            ("Результат пишется в комментарий (ссылка Яндекс.Диск), не в отдельное поле", False),
            ("Количество изображений/артикулов/ID заполняется исполнителем постфактум", False),
            ("В Redmine нет полей: артикул (SKU-код), прямая ссылка на фото, тип инфографики", False),
        ],
    ),
    (
        "Главная находка: ТЗ живёт в Excel-файле",
        None,
        [
            ("Всё ТЗ — в xlsx-вложении к задаче, не в полях Redmine", False),
            ("Стул: франклин.xlsx (1.25 МБ); Стол: бенни лдсп.xlsx (4.18 МБ)", False),
            ("В описании задачи — только URL товара на pm.ru и «ТЗ во вложении»", False),
            ("Проблема 1: товар может ещё не быть на сайте (стол — «ещё не завели»)", False),
            ("Проблема 2: пайплайн ожидает структурированные поля, а не свободный Excel", False),
            ("Это ключевое расхождение между текущим процессом и тем, что нужно автоматизировать", False),
        ],
    ),
    (
        "Как выглядит текущий поток задачи",
        "То, что реально делает менеджер и дизайнер сейчас",
        [
            ("Менеджер заводит задачу: название, категория, URL товара, прикрепляет xlsx с ТЗ", False),
            ("Дизайнер открывает xlsx, читает ТЗ: варианты, размеры, тексты, фото", False),
            ("Дизайнер делает инфографику в Photoshop/Figma вручную по шаблону", False),
            ("Результат грузится на Яндекс.Диск, ссылка вставляется в комментарий задачи", False),
            ("Менеджер проверяет, ставит статус «Готово» и заполняет счётчики изображений/артикулов", False),
            ("Связанная задача на Маркетплейсы создаётся отдельно — для публикации", False),
        ],
    ),
    (
        "Что автоматизирует пайплайн (уточнённое понимание)",
        None,
        [
            ("Читает задачу из Redmine и извлекает данные для обработки", False),
            ("Нормализует и сжимает тексты под лимиты шаблона (LLM)", False),
            ("Выбирает нужный шаблон в Figma по типу карточки", False),
            ("Заполняет шаблон: текст, изображения, цвета", False),
            ("Экспортирует PNG, грузит в хранилище", False),
            ("Пишет ссылку-результат обратно в Redmine, обновляет статус", False),
            ("НЕ автоматизирует: создание 3D-рендеров, сложные размерные схемы, ручные доп. кадры", False),
        ],
    ),
    (
        "Вопросы для созвона — Блок 1",
        "Excel-файл с ТЗ: самое важное",
        [
            ("1. Можешь показать содержимое xlsx по стулу или столу? Нам нужно понять структуру", False),
            ("   — Одинакова ли структура xlsx для всех задач категории?", True),
            ("   — Или каждый менеджер заполняет по-своему?", True),
            ("2. Есть ли шаблон xlsx, которому следуют все? Если да — можно парсить автоматически", False),
            ("3. Готова ли команда на пилоте переносить данные из xlsx в поля Redmine?", False),
            ("   — Это даст пайплайну структурированный вход без парсинга Excel", True),
            ("   — Или обязательно сохранить xlsx-формат?", True),
        ],
    ),
    (
        "Вопросы для созвона — Блок 2",
        "Что производится на выходе",
        [
            ("4. Пайплайн делает одно изображение на вариант или один комплект на артикул?", False),
            ("   — Стул: 1 артикул, 8 вариантов → пайплайн делает 8 изображений или 48?", True),
            ("   — Или пилот начинаем с одного «типового» изображения на артикул?", True),
            ("5. Что такое «одно изображение» в контексте инфографики?", False),
            ("   — Один слайд карточки (например, размерная схема)?", True),
            ("   — Или весь комплект слайдов для одного варианта?", True),
            ("6. Есть ли фиксированный набор слайдов для стула? Сколько их и что на каждом?", False),
        ],
    ),
    (
        "Вопросы для созвона — Блок 3",
        "Поля в Redmine и структура задачи",
        [
            ("7. Стол Бенни — 2 артикула в одной задаче. Для пилота задачи будут заводиться иначе?", False),
            ("   — Нужен регламент: «1 задача = 1 артикул» — кто и когда это контролирует?", True),
            ("8. Готова ли добавить 2–3 новых поля в Redmine для пилота?", False),
            ("   — Артикул (SKU-код товара)", True),
            ("   — Прямой URL главного фото", True),
            ("   — Тип инфографики (размеры / цвета / benefits / hero)", True),
            ("9. Результат сейчас пишется в комментарий. Договоримся писать в отдельное поле «Рендер URL»?", False),
            ("   — Это позволит пайплайну находить результат автоматически", True),
        ],
    ),
    (
        "Вопросы для созвона — Блок 4",
        "Приёмка и Definition of Done",
        [
            ("10. Кто проверяет результат пилота — ты, дизайнер, коммерческий отдел?", False),
            ("11. Что является блокером (без этого не принимаем)?", False),
            ("    — Обрезанный текст, неверный шаблон, неверный цвет фона?", True),
            ("    — Или достаточно «похоже на правду» для первых задач?", True),
            ("12. Какой процент задач без правок считаем успехом пилота?", False),
            ("    — Например: 80% задач приняты без доработки → переходим к мягкой мебели", True),
        ],
    ),
    (
        "Предлагаемые следующие шаги",
        None,
        [
            ("Ника показывает один xlsx с ТЗ — оцениваем структуру", False),
            ("Договариваемся: поля Redmine vs. парсинг xlsx (влияет на сроки разработки)", False),
            ("Фиксируем: что пайплайн производит на одну задачу (1 изображение? 1 вариант? весь комплект?)", False),
            ("Добавляем поля в Redmine для пилота (можно сделать быстро)", False),
            ("Запускаем пилот: первые 3–5 задач вручную контролируем вместе", False),
            ("По результатам пилота: корректируем и масштабируем", False),
        ],
    ),
]


class Deck(FPDF):
    def __init__(self, font_path: Path) -> None:
        super().__init__(format="A4")
        self.font_path = font_path
        self.set_auto_page_break(auto=True, margin=20)

    def header(self) -> None:  # noqa: ANN401
        return

    def footer(self) -> None:
        self.set_y(-14)
        self.set_font("DocFont", "", 8)
        self.set_text_color(130, 130, 130)
        self.cell(0, 8, f"PM-RU Content Agent  |  Созвон 21 апреля 2026  |  Стр. {self.page_no()}", align="C")


def build_pdf(font_path: Path, out: Path) -> None:
    pdf = Deck(font_path)
    pdf.add_font("DocFont", "", str(font_path))

    for title, subtitle, bullets in SLIDES:
        pdf.add_page()

        # Title
        pdf.set_font("DocFont", "", 17)
        pdf.set_text_color(15, 55, 110)
        pdf.multi_cell(0, 10, title)

        # Subtitle
        if subtitle:
            pdf.set_font("DocFont", "", 10)
            pdf.set_text_color(100, 100, 100)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 6, subtitle)

        pdf.ln(4)

        # Horizontal rule simulation
        pdf.set_draw_color(180, 180, 200)
        pdf.set_line_width(0.3)
        pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 170, pdf.get_y())
        pdf.ln(4)

        # Bullets
        margin_l = pdf.l_margin
        for text, is_sub in bullets:
            if is_sub:
                pdf.set_font("DocFont", "", 9)
                pdf.set_text_color(80, 80, 80)
                pdf.set_left_margin(margin_l + 8)
                pdf.set_x(margin_l + 8)
                pdf.multi_cell(0, 5.5, f"  {text}")
                pdf.set_left_margin(margin_l)
            else:
                pdf.set_font("DocFont", "", 11)
                pdf.set_text_color(25, 25, 25)
                pdf.set_x(margin_l)
                pdf.multi_cell(0, 6.5, f"• {text}")
            pdf.ln(0.5)

    out.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out))


def main() -> int:
    try:
        fp = _font_path()
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 1
    build_pdf(fp, OUT_PATH)
    print(f"Wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
