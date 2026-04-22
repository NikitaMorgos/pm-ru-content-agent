"""Start the PM-RU Content Agent admin panel."""
import subprocess
import sys
import webbrowser
import time

PORT = 8001
URL = f"http://localhost:{PORT}/admin"

print("=" * 55)
print("  PM-RU Content Agent — Admin Panel")
print("=" * 55)
print(f"\n  Запускаю сервер на {URL}")
print("  Для остановки нажмите Ctrl+C\n")

try:
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "content_agent.main:app",
         "--host", "127.0.0.1", "--port", str(PORT)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    # Wait for startup
    for line in proc.stdout:
        text = line.decode("utf-8", errors="replace").strip()
        if text:
            print(" ", text)
        if "Application startup complete" in text:
            break

    # Open browser
    time.sleep(0.5)
    print(f"\n  Открываю браузер: {URL}\n")
    webbrowser.open(URL)

    # Stream remaining output
    for line in proc.stdout:
        text = line.decode("utf-8", errors="replace").strip()
        if text:
            print(" ", text)

except KeyboardInterrupt:
    print("\n  Остановлено.")
    proc.terminate()
