"""
Smoke test: создать один FillJob вручную и проверить, что плагин его обрабатывает.

Запуск:
    uv run python scripts/test_fill_job.py

Предварительно:
  1. Бэкенд запущен на localhost:8000
  2. Figma-плагин запущен и нажат Start
  3. Figma-файл 6ftFaqPgnvCbCmyjzxDcKI открыт
"""
import time
import uuid

import httpx

BACKEND = "http://localhost:8000/api/v1"

# Тестовый FillJob — превью стула (190870_1.1, frame_id=4:2387)
TEST_JOB_PAYLOAD = {
    "id": str(uuid.uuid4()),
    "job_id": "smoke-test-001",
    "file_key": "6ftFaqPgnvCbCmyjzxDcKI",
    "frame_id": "4:2387",
    "slide_type": "preview",
    "slide_index": 0,
    "text_fills": {
        "4:2391": "ТЕСТ БРЕНД",
        "4:2393": "стул",
        "4:2394": "Максимальная нагрузка 120 кг",
        "4:2418": "Прост в уходе",
        "4:2419": "Износостойкий микровелюр",
    },
    "image_fills": {},
    "status": "pending",
}


def main() -> None:
    print("=== PM-RU Figma Plugin Smoke Test ===\n")

    # 1. Создаём FillJob напрямую в БД через debug-endpoint
    print("1. Создаём тестовый FillJob через API...")
    r = httpx.post(f"{BACKEND}/fill-jobs/debug/create", json=TEST_JOB_PAYLOAD, timeout=10)
    if r.status_code not in (200, 201):
        print(f"   ОШИБКА: {r.status_code} {r.text}")
        print("   Возможно, debug-endpoint не включён. Создай FillJob через psql напрямую.")
        return
    job = r.json()
    job_id = job["id"]
    print(f"   OK — Job ID: {job_id}")

    # 2. Ждём, пока плагин обработает
    print("\n2. Ожидаем обработки плагином (макс. 2 мин)...")
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        r = httpx.get(f"{BACKEND}/fill-jobs/{job_id}", timeout=10)
        status_data = r.json()
        status = status_data.get("status")
        print(f"   статус: {status}", end="\r")

        if status == "done":
            print(f"\n\n   ✓ Готово! PNG сохранён по ключу: {status_data['result_storage_key']}")
            break
        if status == "error":
            print(f"\n\n   ✗ Ошибка: {status_data['error_message']}")
            break

        time.sleep(3)
    else:
        print("\n\n   Таймаут — плагин не ответил за 2 минуты.")
        print("   Проверь: 1) плагин запущен 2) Figma-файл открыт 3) нажата кнопка Start")


if __name__ == "__main__":
    main()
