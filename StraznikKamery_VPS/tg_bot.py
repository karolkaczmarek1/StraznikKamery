import os
import json
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import history

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
    try:
        stats_msg = history.get_stats_last_7_days()
        await update.message.reply_text(stats_msg, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Error reading stats: {e}")
        await update.message.reply_text("Wystąpił błąd podczas odczytu statystyk.")

if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN:
        logging.error("TELEGRAM_BOT_TOKEN not set!")
        exit(1)
        
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("stats", stats_command))
    
    logging.info("Starting Telegram bot...")
    app.run_polling()
