import os
import json
import logging
from datetime import datetime, timezone
import requests
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TIMEOUT_MINUTES = int(os.getenv("WATCHDOG_TIMEOUT_MINUTES", 15))

STATUS_FILE = "status.json"
WATCHDOG_STATE_FILE = "watchdog_state.json"
HISTORY_FILE = "history.jsonl"

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        logging.error(f"Failed to send telegram message: {e}")

def main():
    if not os.path.exists(STATUS_FILE):
        return

    with open(STATUS_FILE, "r", encoding="utf-8") as f:
        status_data = json.load(f)

    last_seen_str = status_data.get("last_seen_server")
    if not last_seen_str:
        return

    # Parse ISO format datetime
    try:
        last_seen = datetime.fromisoformat(last_seen_str.replace("Z", "+00:00"))
    except ValueError:
        logging.error("Invalid date format in status.json")
        return

    now = datetime.now(timezone.utc)
    diff = now - last_seen
    diff_minutes = diff.total_seconds() / 60.0

    # Load watchdog state
    state = {"alert_active": False}
    if os.path.exists(WATCHDOG_STATE_FILE):
        with open(WATCHDOG_STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)

    if diff_minutes > TIMEOUT_MINUTES:
        if not state.get("alert_active"):
            from zoneinfo import ZoneInfo
            now_pl = now.astimezone(ZoneInfo("Europe/Warsaw"))
            time_str = now_pl.strftime("%Y-%m-%d %H:%M:%S")
            msg = f"🚨 *Serwer Alert*\nCzas (PL): `{time_str}`\nBrak komunikacji z czujnikiem ESP od {int(diff_minutes)} minut!"
            send_telegram(msg)
            
            # Log to history
            alert = {
                "type": "SENSOR_OFFLINE",
                "source": "server",
                "server_time": now.isoformat(),
                "details": f"No contact for {int(diff_minutes)} minutes"
            }
            with open(HISTORY_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(alert) + "\n")
                
            state["alert_active"] = True
            with open(WATCHDOG_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f)
    else:
        if state.get("alert_active"):
            from zoneinfo import ZoneInfo
            now_pl = now.astimezone(ZoneInfo("Europe/Warsaw"))
            time_str = now_pl.strftime("%Y-%m-%d %H:%M:%S")
            msg = f"✅ *Serwer Alert*\nCzas (PL): `{time_str}`\nPrzywrócono komunikację z czujnikiem ESP."
            send_telegram(msg)
            
            alert = {
                "type": "SENSOR_ONLINE",
                "source": "server",
                "server_time": now.isoformat(),
                "details": "Contact restored"
            }
            with open(HISTORY_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(alert) + "\n")
                
            state["alert_active"] = False
            with open(WATCHDOG_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f)

if __name__ == "__main__":
    main()
