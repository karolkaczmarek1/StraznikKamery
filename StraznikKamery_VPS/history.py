import os
import json
from datetime import datetime, timedelta
import fcntl
from collections import defaultdict
from zoneinfo import ZoneInfo

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_DIR = os.path.join(BASE_DIR, "history")

def append_to_daily_history(record):
    now = datetime.now(ZoneInfo("Europe/Warsaw"))
    year_month = now.strftime("%Y-%m")
    day = now.strftime("%d")

    month_dir = os.path.join(HISTORY_DIR, year_month)
    os.makedirs(month_dir, exist_ok=True)

    file_path = os.path.join(month_dir, f"{day}.json")

    # Add record type and timestamp if not present
    record['saved_at'] = now.isoformat()

    try:
        with open(file_path, "a", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    except Exception as e:
        print(f"Error writing to history: {e}")

def get_stats_last_7_days():
    now = datetime.now(ZoneInfo("Europe/Warsaw"))
    alerts = []
    daily_pings = {}

    for i in range(7):
        dt = now - timedelta(days=i)
        year_month = dt.strftime("%Y-%m")
        day = dt.strftime("%d")
        date_str = dt.strftime("%Y-%m-%d")

        file_path = os.path.join(HISTORY_DIR, year_month, f"{day}.json")

        if os.path.exists(file_path):
            pings_for_day = []
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        try:
                            record = json.loads(line)

                            if "type" in record:
                                alerts.append(record)

                            if "esp_data" in record and "ping_time_ms" in record["esp_data"]:
                                ping_val = record["esp_data"]["ping_time_ms"]
                                if isinstance(ping_val, (int, float)):
                                    pings_for_day.append(ping_val)
                        except json.JSONDecodeError:
                            continue
            except Exception:
                pass

            if pings_for_day:
                daily_pings[date_str] = sum(pings_for_day) / len(pings_for_day)

    # Sort alerts by time
    def get_alert_time(alert):
        if "server_time" in alert:
            return alert["server_time"]
        elif "saved_at" in alert:
            return alert["saved_at"]
        return ""

    alerts.sort(key=get_alert_time)

    # Generate ASCII bar chart
    chart = "Brak danych o pingu z ostatnich 7 dni."
    if daily_pings:
        days_list = []
        for i in range(7):
            dt = now - timedelta(days=6 - i) # chronological order left to right
            date_str = dt.strftime("%Y-%m-%d")
            days_list.append(dt.strftime("%d"))


        lines = []
        for level in range(50, -1, -10):
            line = f"{level:02} "
            for i in range(7):
                dt = now - timedelta(days=6 - i)
                date_str = dt.strftime("%Y-%m-%d")

                ping = daily_pings.get(date_str)
                if ping is not None and ping >= level:
                    line += "## "
                else:
                    line += "   "
            lines.append(line.rstrip())

        x_axis = "   " + " ".join(days_list)
        lines.append(x_axis)
        chart = "\n".join(lines)

    # Format alerts
    alerts_text = "Brak alarmów w ostatnich 7 dniach."
    if alerts:
        alerts_lines = []
        for alert in alerts[-30:]: # Keep max 30 alerts limit for msg size, even if 7 days
            time_str = alert.get("server_time", alert.get("saved_at", ""))
            try:
                dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                dt_pl = dt.astimezone(ZoneInfo("Europe/Warsaw"))
                formatted_time = dt_pl.strftime("%Y-%m-%d %H:%M")
            except:
                formatted_time = time_str

            alerts_lines.append(f"[{formatted_time}] {alert.get('type', 'UNKNOWN')}")

        alerts_text = "\n".join(alerts_lines)

    stats_msg = f"📊 *Statystyki (Ostatnie 7 dni)*\n\n*Średni ping (ms):*\n```\n{chart}\n```\n\n*Ostatnie alarmy:*\n```\n{alerts_text}\n```"
    return stats_msg
