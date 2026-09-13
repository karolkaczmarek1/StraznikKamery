#!/bin/bash
# Skrypt do uruchamiania serwisów Strażnika Kamery

cd ~/StraznikKamery
source venv/bin/activate

# Zabij stare instancje (opcjonalne)
pkill -f api_server.py
pkill -f tg_bot.py

# Uruchom nowe
nohup python api_server.py > api.log 2>&1 &
nohup python tg_bot.py > bot.log 2>&1 &

echo "Uruchamianie API serwera..."
echo "Uruchamianie Telegram Bota..."
echo "Gotowe. Pamiętaj o dodaniu watchdoga i healthchecks do crontaba!"
