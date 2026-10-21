"""자동 촬영과 달력 웹페이지를 함께 실행한다."""
import json
import threading

import capture
from calendar_app import create_app

if __name__ == "__main__":
    with open("config.json", encoding="utf-8") as f:
        cfg = json.load(f)
    threading.Thread(target=capture.run, args=(cfg,), daemon=True).start()
    print(f"달력: http://127.0.0.1:{cfg['port']}")
    create_app(cfg["photo_dir"]).run(host="127.0.0.1", port=cfg["port"])
