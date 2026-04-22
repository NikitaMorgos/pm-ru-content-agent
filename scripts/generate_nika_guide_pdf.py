"""Generate the PM-RU Content Agent guide PDF for Nika."""
from __future__ import annotations

import datetime
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src"))

from fpdf import FPDF

OUT_PATH = pathlib.Path(__file__).parent.parent / "docs" / "nika_content_agent_guide.pdf"

BRAND = (59, 107, 240)       # brand blue
DARK = (30, 41, 59)          # slate-800
MEDIUM = (71, 85, 105)       # slate-600
LIGHT = (148, 163, 184)      # slate-400
BG_LIGHT = (248, 250, 252)   # slate-50
BG_BLUE = (224, 231, 255)    # indigo-100
GREEN = (22, 163, 74)
GREEN_BG = (220, 252, 231)


FONT_DIR = pathlib.Path("C:/Windows/Fonts")
FONT_REGULAR = str(FONT_DIR / "arial.ttf")
FONT_BOLD    = str(FONT_DIR / "arialbd.ttf")
FONT_ITALIC  = str(FONT_DIR / "ariali.ttf")


class PDF(FPDF):
    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.add_font("Arial", "", FONT_REGULAR)
        self.add_font("Arial", "B", FONT_BOLD)
        self.add_font("Arial", "I", FONT_ITALIC)
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(20, 20, 20)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_fill_color(255, 255, 255)
        self.set_draw_color(226, 232, 240)
        self.set_line_width(0.3)
        self.set_y(10)
        self.set_font("Arial", "B", 8)
        self.set_text_color(*LIGHT)
        self.cell(0, 6, "PM-RU Content Agent  |  Руководство пользователя", align="C")
        self.ln(4)
        self.line(20, 18, 190, 18)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "", 8)
        self.set_text_color(*LIGHT)
        self.cell(0, 5, f"Стр. {self.page_no()}  |  {datetime.date.today().strftime('%d.%m.%Y')}", align="C")

    # ── Helpers ────────────────────────────────────────────────────────────────

    def section_title(self, n: str, title: str):
        self.ln(6)
        self.set_fill_color(*BRAND)
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", "B", 11)
        self.cell(7, 7, n, fill=True, align="C")
        self.set_fill_color(*BG_LIGHT)
        self.set_text_color(*DARK)
        self.cell(0, 7, f"  {title}", fill=True)
        self.ln(8)

    def body(self, text: str, bold: bool = False):
        self.set_font("Arial", "B" if bold else "", 10)
        self.set_text_color(*DARK if bold else MEDIUM)
        self.multi_cell(0, 5.5, text)
        self.ln(1)

    def bullet(self, text: str, indent: int = 8):
        self.set_font("Arial", "", 9.5)
        self.set_text_color(*MEDIUM)
        x = self.get_x()
        self.set_x(20 + indent)
        self.cell(4, 5, chr(149))
        self.multi_cell(0, 5, text)
        self.set_x(x)

    def step_row(self, num: str, title: str, desc: str, highlight: bool = False):
        bg = BG_BLUE if highlight else BG_LIGHT
        y = self.get_y()
        self.set_fill_color(*bg)
        self.rect(20, y, 170, 14, "F")
        self.set_xy(22, y + 1.5)
        self.set_fill_color(*BRAND)
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", "B", 8)
        self.cell(8, 8, num, fill=True, align="C")
        self.set_text_color(*DARK)
        self.set_font("Arial", "B", 9.5)
        self.cell(50, 8, f"  {title}")
        self.set_text_color(*MEDIUM)
        self.set_font("Arial", "", 9)
        self.cell(0, 8, desc)
        self.ln(15)

    def kv_row(self, key: str, req: str, desc: str, example: str):
        y = self.get_y()
        self.set_fill_color(*BG_LIGHT)
        self.rect(20, y, 170, 8, "F")
        self.set_xy(22, y + 1.5)
        self.set_text_color(*DARK)
        self.set_font("Arial", "B", 9)
        self.cell(38, 5, key)
        if req == "✱":
            self.set_text_color(220, 38, 38)
        elif req == "➕":
            self.set_text_color(234, 88, 12)
        else:
            self.set_text_color(*LIGHT)
        self.set_font("Arial", "B", 9)
        self.cell(10, 5, req, align="C")
        self.set_text_color(*MEDIUM)
        self.set_font("Arial", "", 9)
        self.cell(60, 5, desc)
        self.set_text_color(*DARK)
        self.set_font("Arial", "I", 8.5)
        self.cell(0, 5, example)
        self.ln(9)

    def notice(self, text: str, color: tuple = None):
        c = color or BG_BLUE
        self.set_fill_color(*c)
        self.set_text_color(*DARK)
        self.set_font("Arial", "", 9.5)
        self.multi_cell(0, 5.5, text, fill=True, border=0)
        self.ln(3)


def build() -> None:
    pdf = PDF()
    pdf.add_page()

    # ── Cover ──────────────────────────────────────────────────────────────────
    pdf.set_fill_color(*BRAND)
    pdf.rect(0, 0, 210, 65, "F")
    pdf.set_y(18)
    pdf.set_font("Arial", "B", 24)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, "PM-RU Content Agent", align="C")
    pdf.ln(12)
    pdf.set_font("Arial", "", 14)
    pdf.set_text_color(199, 210, 254)
    pdf.cell(0, 8, "Руководство пользователя", align="C")
    pdf.ln(8)
    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(165, 180, 252)
    pdf.cell(0, 6, f"Версия MVP  |  {datetime.date.today().strftime('%d %B %Y')}", align="C")
    pdf.set_y(75)

    # ── What is this ──────────────────────────────────────────────────────────
    pdf.section_title("О", "Что такое Content Agent?")
    pdf.body(
        "PM-RU Content Agent — это система автоматической сборки карточек товаров "
        "для маркетплейсов. Менеджер заполняет форму ТЗ, нажимает одну кнопку — "
        "и система сама создаёт готовые PNG-слайды по стандартам Figma."
    )
    pdf.ln(2)
    pdf.body("Что происходит автоматически:", bold=True)
    pdf.bullet("Проверка и нормализация текстов по стандарту маркетплейса")
    pdf.bullet("Подбор нужного набора слайдов (превью, размеры, УТП, материалы)")
    pdf.bullet("Рендер: PNG-шаблон из Figma + реальные тексты из ТЗ")
    pdf.bullet("Готовые слайды — в браузере, кнопка скачать")

    # ── Pipeline ───────────────────────────────────────────────────────────────
    pdf.section_title("1", "Архитектура пайплайна (9 шагов)")
    pdf.set_font("Arial", "", 9.5)
    pdf.set_text_color(*MEDIUM)
    pdf.cell(0, 5, "Каждое задание проходит 9 шагов последовательно:", align="L")
    pdf.ln(7)

    steps = [
        ("1", "Манифест",          "Данные формы ТЗ → внутренний формат задачи", False),
        ("2", "Валидация",         "Проверка обязательных полей и форматов", False),
        ("3", "Нормализация",      "ИИ нормализует тексты под стиль маркетплейса", False),
        ("4", "Сжатие",            "ИИ обрезает тексты до допустимой длины", False),
        ("5", "Выбор шаблона",     "По категории выбирается набор слайдов из Figma", True),
        ("6", "Рендер слайдов",    "Локальный кэш PNG + наложение текстов (Pillow)", True),
        ("7", "Экспорт PNG",       "Финальные PNG готовы к раздаче", False),
        ("8", "Загрузка",          "Сохранение в облачное хранилище", False),
        ("✓", "Готово",            "Слайды доступны для скачивания в панели", False),
    ]
    for num, title, desc, hl in steps:
        pdf.step_row(num, title, desc, hl)

    pdf.notice(
        "  Шаги 5-6 (синие) работают офлайн — шаблоны из Figma скачиваются один раз "
        "и кэшируются локально. Figma API не вызывается при каждом рендере."
    )

    # ── How to use ─────────────────────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("2", "Инструкция для менеджера")

    pdf.body("Как создать задание:", bold=True)
    instructions = [
        ("① Открой панель",   "Перейди по адресу панели в браузере"),
        ("② Новое задание",   "Нажми синюю кнопку «Новое задание» (правый верхний угол)"),
        ("③ Выбери категорию","Стол или Стул — форма подстраивается автоматически"),
        ("④ Заполни форму",   "Артикул, вариант, бренд, название, размеры, материалы, УТП, фото"),
        ("⑤ Передай",        "Нажми «Передать в пайплайн» — задание появится на дашборде"),
        ("⑥ Жди и скачай",   "Когда статус «Готово» — нажми «Слайд 1», «Слайд 2» для скачивания"),
    ]
    for step, desc in instructions:
        y = pdf.get_y()
        pdf.set_fill_color(*BG_LIGHT)
        pdf.rect(20, y, 170, 11, "F")
        pdf.set_xy(22, y + 2)
        pdf.set_text_color(*BRAND)
        pdf.set_font("Arial", "B", 10)
        pdf.cell(30, 6, step)
        pdf.set_text_color(*MEDIUM)
        pdf.set_font("Arial", "", 9.5)
        pdf.cell(0, 6, desc)
        pdf.ln(13)

    # ── Fields ─────────────────────────────────────────────────────────────────
    pdf.ln(2)
    pdf.section_title("3", "Справочник полей ТЗ")
    pdf.ln(1)

    # Header row
    y = pdf.get_y()
    pdf.set_fill_color(*BRAND)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 8.5)
    pdf.rect(20, y, 170, 7, "F")
    pdf.set_xy(22, y + 1)
    pdf.cell(38, 5, "Поле")
    pdf.cell(10, 5, "Обяз.", align="C")
    pdf.cell(60, 5, "Что писать")
    pdf.cell(0, 5, "Пример")
    pdf.ln(9)

    rows = [
        ("Артикул",          "✱",  "Артикул из Redmine",              "184109"),
        ("Вариант / цвет",   "",   "Цвет или модификация",            "Белый глянец"),
        ("Бренд",            "✱",  "Название бренда (caps)",          "БЕННИ"),
        ("Название товара",  "✱",  "Полное название",                 "Стол обеденный раскладной"),
        ("Ш × Г × В (см)",   "✱",  "Три размера в сантиметрах",       "120 x 75 x 75"),
        ("Высота сиденья",   "",   "Только для стульев",              "46"),
        ("Столешница",       "",   "Материал столешницы",             "ЛДСП 22 мм"),
        ("Цвет/отделка",     "",   "Цвет поверхности",                "Дуб Сонома"),
        ("Ножки",            "",   "Материал ножек",                  "Металл, порошковая"),
        ("УТП 1–5",          "➕", "3–5 преимуществ товара",          "Антисцарапин покрытие"),
        ("Фото URL 1–5",     "➕", "Прямые ссылки на изображения",    "https://..."),
    ]
    for key, req, desc, ex in rows:
        pdf.kv_row(key, req, desc, ex)

    pdf.ln(3)
    pdf.set_font("Arial", "", 8.5)
    pdf.set_text_color(*MEDIUM)
    pdf.cell(0, 4, "✱ — обязательное поле    ➕ — настоятельно рекомендуется заполнить")
    pdf.ln(6)

    # ── Statuses ───────────────────────────────────────────────────────────────
    pdf.section_title("4", "Статусы заданий")
    statuses = [
        ("Ожидает",  (148, 163, 184), "Задание принято, пайплайн запускается"),
        ("В работе", (59, 130, 246),  "Идёт обработка — виден текущий шаг"),
        ("Готово",   (22, 163, 74),   "Слайды собраны, доступны для скачивания"),
        ("Ошибка",   (220, 38, 38),   "Текст ошибки виден в карточке. Создайте задание заново."),
    ]
    for label, color, desc in statuses:
        y = pdf.get_y()
        pdf.set_fill_color(*BG_LIGHT)
        pdf.rect(20, y, 170, 9, "F")
        pdf.set_fill_color(*color)
        pdf.circle(26, y + 4.5, 2.5, "F")
        pdf.set_xy(31, y + 2)
        pdf.set_text_color(*DARK)
        pdf.set_font("Arial", "B", 9.5)
        pdf.cell(28, 5, label)
        pdf.set_text_color(*MEDIUM)
        pdf.set_font("Arial", "", 9)
        pdf.cell(0, 5, desc)
        pdf.ln(11)

    # ── FAQ ────────────────────────────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("5", "Часто задаваемые вопросы")

    faqs = [
        ("Сколько времени занимает задание?",
         "~15–60 сек для 4–8 слайдов. Если шаблоны закэшированы — рендер занимает 3–5 сек без обращений к Figma."),
        ("Можно создавать несколько заданий одновременно?",
         "Да. Все задания обрабатываются параллельно и отображаются на дашборде."),
        ("Что делать, если статус «Ошибка»?",
         "Прочитай текст ошибки в карточке. Обычно причина — некорректный URL фото или временная недоступность сети. Создай задание заново."),
        ("Где хранятся готовые PNG?",
         "Сейчас — временно на сервере. На следующем этапе подключается постоянное хранилище (Yandex S3). Скачивай сразу через кнопки «Слайд N» в карточке."),
        ("Как обновить шаблоны если дизайнер изменил Figma?",
         "Скажи разработчику запустить команду: python scripts/sync_figma_cache.py --force\nЭто скачает актуальные шаблоны. Обычные рендеры работают из кэша без Figma API."),
        ("Нужен ли интернет для работы?",
         "Только для отправки задания и скачивания результатов. Сам рендер (шаг 6) работает полностью офлайн — шаблоны хранятся локально."),
    ]

    for q, a in faqs:
        pdf.set_x(20)
        pdf.set_font("Arial", "B", 10)
        pdf.set_text_color(*DARK)
        pdf.multi_cell(0, 5.5, f"Q: {q}")
        pdf.set_x(20)
        pdf.set_font("Arial", "", 9.5)
        pdf.set_text_color(*MEDIUM)
        pdf.multi_cell(0, 5, f"A: {a}")
        pdf.ln(4)

    # ── Admin notes ────────────────────────────────────────────────────────────
    pdf.section_title("6", "Заметки для администратора")
    admin_notes = [
        ("Запуск сервера",
         "python start_admin.py\nОткроет браузер автоматически на http://localhost:8001/admin"),
        ("Обновление Figma-кэша",
         "python scripts/sync_figma_cache.py\nЗапускать при изменении дизайна в Figma"),
        ("Структура хранилища",
         "Шаблоны: src/content_agent/integrations/figma/template_cache/\nРезультаты (временные): %TEMP%/slide_*.png"),
        ("Что ещё нужно подключить",
         "- Постоянное хранилище (S3/Yandex Disk) — шаг Upload\n"
         "- Нормализация текстов через LLM (шаги 3–4)\n"
         "- Интеграция с Redmine для автозапуска по задачам"),
    ]
    for title, body in admin_notes:
        pdf.set_font("Arial", "B", 10)
        pdf.set_text_color(*DARK)
        pdf.cell(0, 5.5, title)
        pdf.ln(6)
        pdf.set_font("Arial", "", 9.5)
        pdf.set_text_color(*MEDIUM)
        pdf.multi_cell(0, 5, body)
        pdf.ln(3)

    pdf.output(str(OUT_PATH))
    print(f"PDF saved: {OUT_PATH}")


if __name__ == "__main__":
    build()
