"""Generate a short PDF deck for the content team (Russian text, UTF-8)."""

from __future__ import annotations

import sys
from pathlib import Path

from fpdf import FPDF

# Project root: .../PM-RU_ContentAgent
ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "docs" / "PM-RU_Content_Agent_presentation.pdf"

# Typical Windows fonts with Cyrillic
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


SLIDES: list[tuple[str, list[str]]] = [
    (
        "PM-RU Content Agent",
        [
            "Автоматическая сборка визуала маркетплейс-карточки по задаче из трекера.",
            "Шаблон в Figma → проверки → экспорт → ссылка на результат в задаче.",
        ],
    ),
    (
        "Зачем это нужно",
        [
            "Снизить ручную рутину на повторяемых карточках одного типа.",
            "Дать предсказуемый результат: один контракт полей — один маршрут обработки.",
            "Контроль остаётся у человека: трекер — источник правды; ИИ — вспомогательный слой, не «генератор с нуля».",
        ],
    ),
    (
        "Роли систем",
        [
            "Redmine — задача, статусы, обязательные поля (тип карточки, артикул, картинка и т.д.), запись результата.",
            "Figma — эталон макета: слоты текста/картинок, шаблон по типу карточки.",
            "Пайплайн (сервис + очередь) — забирает задачу, валидирует данные, при необходимости нормализует текст, заполняет шаблон, экспортирует PNG, грузит в хранилище.",
            "LLM — вспомогательно: нормализация и сжатие текстов под ограничения макета.",
            "Хранилище (S3-совместимое) — файл результата (в т.ч. с участием артикула в ключе).",
        ],
    ),
    (
        "Поток end-to-end",
        [
            "1) В Redmine одна задача с заполненными согласованными полями.",
            "2) Запуск обработки по ID задачи.",
            "3) Чтение полей и сбор внутреннего манифеста (единая структура на весь прогон).",
            "4) QA-правила по типу карточки; при ошибках — остановка с причиной.",
            "5) При необходимости — LLM: подогнать формулировки под лимиты.",
            "6) Выбор и заполнение шаблона Figma → экспорт PNG → загрузка → запись в Redmine (ссылка на рендер).",
        ],
    ),
    (
        "MVP: одна задача = один артикул",
        [
            "Один issue в Redmine = одна карточка = один SKU в поле артикула.",
            "Один прогон пайплайна, один результат, одна ссылка; понятные статусы успех/ошибка.",
            "Меньше рисков: не нужно проектировать частичный успех и несколько рендеров на одну задачу.",
        ],
    ),
    (
        "Позже: одна задача = несколько артикулов",
        [
            "Орг. вариант: несколько задач в трекере + удобный массовый запуск — пайплайн тот же.",
            "Родитель + подзадачи по артикулу: триггер на подзадачи, отчёт по каждой.",
            "Одна задача со списком SKU: шаг «распаковки» в несколько прогонов — сложнее статусы и ошибки.",
            "ИИ «разбивает» описание на подзадачи: возможно как черновик, но нужны валидация и подтверждение человеком.",
        ],
    ),
    (
        "Типы карточек (рамка продукта)",
        [
            "Ограниченный набор типов: hero, dimensions, colors, simple_benefit.",
            "У каждого типа — свои правила и шаблоны.",
        ],
    ),
    (
        "Что зафиксировать с отделом контента (бриф)",
        [
            "Единица работы: на MVP — одна задача = один артикул.",
            "Приоритет типов карточек и ожидаемый объём (пилот).",
            "Обязательные поля в Redmine: без чего задачу не запускаем.",
            "Источники фото и текстов; что в первой версии не автоматизируем.",
            "Приёмка: кто смотрит результат; что блокирует выпуск.",
            "Границы ИИ: нормализация/сжатие под макет, а не выдумывание контента без входных данных.",
            "Итог встречи: одна страница — Definition of Done, минимум полей, роли, ожидания.",
        ],
    ),
]


class Deck(FPDF):
    def __init__(self, font_path: Path) -> None:
        super().__init__(format="A4")
        self.font_path = font_path
        self.set_auto_page_break(auto=True, margin=18)

    def header(self) -> None:  # noqa: ANN401
        return

    def footer(self) -> None:
        self.set_y(-14)
        self.set_font("DocFont", "", 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, f"Стр. {self.page_no()}", align="C")


def build_pdf(font_path: Path, out: Path) -> None:
    pdf = Deck(font_path)
    pdf.add_font("DocFont", "", str(font_path))
    pdf.set_font("DocFont", "", 11)

    for title, bullets in SLIDES:
        pdf.add_page()
        pdf.set_font("DocFont", "", 16)
        pdf.set_text_color(20, 20, 20)
        pdf.multi_cell(0, 9, title)
        pdf.ln(4)
        pdf.set_font("DocFont", "", 11)
        pdf.set_text_color(30, 30, 30)
        for line in bullets:
            pdf.multi_cell(0, 6.5, f"• {line}")
            pdf.ln(1)

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
