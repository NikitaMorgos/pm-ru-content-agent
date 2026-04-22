"""TZ form schemas and in-memory job store."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# ── Pipeline steps (in order) ─────────────────────────────────────────────────

PIPELINE_STEPS = [
    ("build_manifest",    "Создание манифеста"),
    ("validate",          "Валидация"),
    ("normalize",         "Нормализация"),
    ("compress",          "Сжатие текстов"),
    ("select_template",   "Выбор шаблона"),
    ("fill_template",     "Рендер слайдов"),
    ("export_png",        "Экспорт PNG"),
    ("upload",            "Загрузка файлов"),
    ("done",              "Готово"),
]

STEP_NAMES = {k: v for k, v in PIPELINE_STEPS}


# ── TZ form schema ────────────────────────────────────────────────────────────

class TZForm(BaseModel):
    category: Literal["table", "chair"]
    article: str
    variant: str = ""           # цвет / модификация
    brand: str
    product_name: str

    # Dimensions (cm)
    width_cm: float
    depth_cm: float
    height_cm: float
    seat_height_cm: float | None = None   # стулья

    # Materials
    tabletop_material: str = ""   # столешница (столы)
    tabletop_finish: str = ""     # цвет/отделка столешницы
    legs_material: str = ""       # материал ножек
    fabric_type: str = ""         # ткань обивки (стулья)
    frame_material: str = ""      # каркас (стулья)
    max_load: str = ""            # макс. нагрузка

    # UTPs / Benefits
    utp_1: str = ""
    utp_2: str = ""
    utp_3: str = ""
    utp_4: str = ""
    utp_5: str = ""

    # Optional feature flags
    is_extendable: bool = False       # стол-трансформер
    has_antiscratch: bool = False     # антикоготь (стулья)

    # Photos
    photo_url_1: str = ""
    photo_url_2: str = ""
    photo_url_3: str = ""
    photo_url_4: str = ""
    photo_url_5: str = ""


# ── Job record ────────────────────────────────────────────────────────────────

class AdminJob(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    tz: TZForm
    state: str = "pending"          # pending | running | done | error
    current_step: str = ""
    current_step_label: str = ""
    step_index: int = 0             # 0-based, out of len(PIPELINE_STEPS)
    error_message: str = ""
    result_urls: list[str] = Field(default_factory=list)
    celery_task_id: str = ""
    created_at: str = Field(
        default_factory=lambda: datetime.now().strftime("%d %b %Y, %H:%M")
    )


# ── In-memory store ───────────────────────────────────────────────────────────

_jobs: dict[str, AdminJob] = {}


def create_job(tz: TZForm) -> AdminJob:
    job = AdminJob(tz=tz)
    _jobs[job.id] = job
    return job


def get_job(job_id: str) -> AdminJob | None:
    return _jobs.get(job_id)


def list_jobs() -> list[AdminJob]:
    return sorted(_jobs.values(), key=lambda j: j.created_at, reverse=True)


def update_job(job_id: str, **kwargs: object) -> AdminJob | None:
    job = _jobs.get(job_id)
    if job is None:
        return None
    for k, v in kwargs.items():
        setattr(job, k, v)
    return job
