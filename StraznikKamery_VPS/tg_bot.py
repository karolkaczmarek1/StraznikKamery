import os
import json
import statistics
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict

import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

load_dotenv()
logging.basicConfig(level=logging.INFO)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
STATUS_FILE = "status.json"

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists(STATUS_FILE):
        await update.message.reply_text("Brak danych z czujnika (plik statusu nie istnieje).")
        return

    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        last_seen = data.get("last_seen_server")
        esp = data.get("esp_data", {})
        uptime_raw = esp.get("uptime_s", 0)
        
        last_seen_str = "N/A"
        boot_time_str = "N/A"
        uptime_str = f"{uptime_raw} s"
        
        if last_seen:
            try:
                from zoneinfo import ZoneInfo
                from datetime import datetime, timedelta
                dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                dt_pl = dt.astimezone(ZoneInfo("Europe/Warsaw"))
                last_seen_str = dt_pl.strftime("%Y-%m-%d %H:%M:%S")
                
                uptime_int = int(uptime_raw)
                boot_time = dt_pl - timedelta(seconds=uptime_int)
                boot_time_str = boot_time.strftime("%Y-%m-%d %H:%M:%S")
                
                m, s = divmod(uptime_int, 60)
                h, m = divmod(m, 60)
                d, h = divmod(h, 24)
                y, d = divmod(d, 365)
                mo, d = divmod(d, 30)
                
                parts = []
                if y > 0: parts.append(f"{y}y")
                if mo > 0: parts.append(f"{mo}mo")
                if d > 0: parts.append(f"{d}d")
                if h > 0: parts.append(f"{h}h")
                if m > 0: parts.append(f"{m}m")
                parts.append(f"{s}s")
                uptime_str = " ".join(parts)
            except Exception:
                last_seen_str = last_seen
        
        wifi_ssid = esp.get("wifi_ssid", "N/A")
        wifi_rssi = esp.get("wifi_rssi", "N/A")
        internet_ok = esp.get("internet_ok", False)
        ping_time = esp.get("ping_time_ms", "N/A")
        
        msg = (
            f"📊 *Status Strażnika*\n"
            f"Ostatni kontakt: `{last_seen_str}`\n"
            f"Uruchomiono: `{boot_time_str}`\n"
            f"Uptime: `{uptime_str}`\n"
            f"Wi-Fi: `{wifi_ssid}` ({wifi_rssi} dBm)\n"
            f"Internet: `{'OK' if internet_ok else 'BRAK'}` (Ping: {ping_time} ms)"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Error reading status: {e}")
        await update.message.reply_text("Wystąpił błąd podczas odczytu statusu.")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now_pl = datetime.now(ZoneInfo("Europe/Warsaw"))
    today = now_pl.date()

    alarms = []
    daily_pings = defaultdict(list)

    for i in range(30):
        d = today - timedelta(days=i)
        yyyy_mm = d.strftime("%Y-%m")
        dd = d.strftime("%d")
        filepath = os.path.join(".", "history", yyyy_mm, f"{dd}.json")

        if not os.path.exists(filepath):
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    if record.get("type") == "alert":
                        alarms.append(record)
                    elif record.get("type") == "status":
                        ping = record.get("data", {}).get("esp_data", {}).get("ping_time_ms")
                        if isinstance(ping, (int, float)):
                            daily_pings[i].append(ping)
                except Exception:
                    pass

    def format_sd(data):
        if not data:
            return "Brak"
        mean = statistics.mean(data)
        sd = statistics.stdev(data) if len(data) > 1 else 0.0
        return f"{mean:.1f}ms ± {2*sd:.1f}ms"

    msg = "📊 *Statystyki z 30 dni*\n\n"

    msg += "🚨 *Alarmy (ostatnie 30 dni):*\n"
    if not alarms:
        msg += "Brak alarmów.\n"
    else:
        for a in alarms:
            ts = a.get("timestamp", "Nieznany czas")
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Warsaw"))
                ts = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                pass
            alert_type = a.get("alert_data", {}).get("type", "Nieznany")
            msg += f"• `{ts}`: {alert_type}\n"

    msg += "\n📈 *Ping tygodniowy (Średnia ± 2SD):*\n"
    week_3 = []
    for i in range(15, 22): week_3.extend(daily_pings[i])
    week_2 = []
    for i in range(8, 15): week_2.extend(daily_pings[i])
    week_1 = []
    for i in range(1, 8): week_1.extend(daily_pings[i])

    msg += f"Tydzień -3: {format_sd(week_3)}\n"
    msg += f"Tydzień -2: {format_sd(week_2)}\n"
    msg += f"Tydzień -1: {format_sd(week_1)}\n"

    msg += "\n📉 *Ping dzienny (Średnia ± 2SD):*\n"
    for i in range(6, -1, -1):
        d_date = today - timedelta(days=i)
        d_str = d_date.strftime("%Y-%m-%d")
        day_label = "Dziś (-0)" if i == 0 else f"Dzień -{i} ({d_str})"
        msg += f"{day_label}: {format_sd(daily_pings[i])}\n"

    await update.message.reply_text(msg, parse_mode="Markdown")


if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN:
        logging.error("TELEGRAM_BOT_TOKEN not set!")
        exit(1)
        
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("stats", stats_command))
    
    logging.info("Starting Telegram bot...")
    app.run_polling()
