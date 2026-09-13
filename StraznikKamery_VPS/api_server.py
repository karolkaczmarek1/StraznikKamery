import os
import json
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
import requests
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
logging.basicConfig(level=logging.INFO)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
API_SECRET = os.getenv("API_SECRET")

STATUS_FILE = "status.json"
HISTORY_FILE = "history.jsonl"

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("Telegram token or chat_id not set, cannot send message.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        logging.error(f"Failed to send telegram message: {e}")

@app.post("/update")
async def update_status(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or auth_header != f"Bearer {API_SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Save latest status
    from datetime import timezone
    now = datetime.now(timezone.utc)
    status_data = {
        "last_seen_server": now.isoformat(),
        "esp_data": data.get("status", {})
    }
    
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status_data, f, ensure_ascii=False, indent=2)

    # Process alerts
    alerts = data.get("alerts", [])
    if alerts:
        from zoneinfo import ZoneInfo
        now_pl = now.astimezone(ZoneInfo("Europe/Warsaw"))
        time_str = now_pl.strftime("%Y-%m-%d %H:%M:%S")
        for alert in alerts:
            esp_time = alert.get('time')
            msg = f"⚠️ *ESP Alert*\nTyp: `{alert.get('type')}`\nCzas odbioru (PL): `{time_str}`\nCzas z czujnika: `{esp_time}`\nDetale: {alert.get('details', '')}"
            send_telegram(msg)
            
            # Save to history
            alert["server_time"] = now.isoformat()
            alert["source"] = "sensor"
            with open(HISTORY_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(alert) + "\n")

    return {"status": "ok"}

@app.get("/health")
async def health():
    return {"status": "running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
