# Strażnik Kamery - Zasilanie i Internet

System monitorowania prądu i internetu na działce przy użyciu ESP8266 (Lolin NodeMCU v3) i VPS (Mikrus Frog).

## Struktura projektu

Projekt składa się z dwóch części, zgodnie z filozofią UNIX - wiele małych, wyspecjalizowanych narzędzi:

1. **`StraznikKamery_ESP/`** - Kod źródłowy C++ dla mikrokontrolera ESP8266 (Arduino IDE).
2. **`StraznikKamery_VPS/`** - Zestaw skryptów w Pythonie działających na serwerze Mikrus.

## Jak to działa?

1. **ESP8266** cyklicznie testuje łączność z Wi-Fi oraz pinguje zaufane serwery (8.8.8.8, 1.1.1.1).
2. Jeśli wykryje zmianę stanu (np. utrata Wi-Fi, brak pingów, uruchomienie), zapisuje zdarzenie do swojej nieulotnej pamięci `LittleFS` (aby zachować je w przypadku utraty zasilania, bez zbędnej degradacji pamięci cyklicznymi logami).
3. Co minutę ESP8266 wysyła pakiet JSON ze statusem i ewentualnymi alertami na główne API (https://) lub w ramach fallbacku na zapasowe API (http://). Jeśli VPS potwierdzi odbiór (HTTP 200), ESP czyści z pamięci alerty.
4. ESP pinguje też samodzielnie swój dedykowany adres w Healthchecks.io.
5. **Na serwerze VPS** działają 3 niezależne procesy:
   - `api_server.py` - Odbiera dane od ESP, zapisuje bieżący stan do `status.json`. Jeżeli otrzyma nowe alerty, od razu przesyła je na Telegram i archiwizuje w `history.jsonl`.
   - `tg_bot.py` - Bot, który używa prostego long-pollingu, czekając na komendę `/status`. Czyta wtedy plik `status.json` i odpowiada statusem w czasie rzeczywistym.
   - `watchdog.py` - Skrypt odpalany z crona (np. co minutę). Odczytuje `status.json`. Jeśli sygnał od ESP zaginął na więcej niż 10 minut (zależnie od wartości w .env), skrypt podnosi alarm na Telegram.

## Wdrożenie

### 1. Serwer VPS (Mikrus)

```bash
cd ~/StraznikKamery
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edytuj .env i uzupełnij: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID oraz wymyśl API_SECRET
nano .env

# Uruchom skrypty serwera i bota w tle:
bash start.sh
```

Następnie dodaj Watchdog oraz Healthchecks dla VPS do Crona (`crontab -e`), używając przykładu z pliku `crontab.example`.

### 2. ESP8266 (Arduino IDE)

Otwórz folder `StraznikKamery_ESP/` w **Arduino IDE** (kliknij dwukrotnie plik `StraznikKamery_ESP.ino`).

Zanim wgrasz kod, wykonaj dwie rzeczy:
1. **Zainstaluj biblioteki** (Szkic -> Dołącz bibliotekę -> Zarządzaj bibliotekami):
   - `ArduinoJson` (autor: Benoit Blanchon)
   - `NTPClient` (autor: Fabrice Weinberg)
   - `ESP8266Ping` (autor: Marian Craciunescu)

2. **Skonfiguruj płytkę i pamięć**:
   - W Narzędzia -> Płytka wybierz **NodeMCU 1.0 (ESP-12E Module)** (lub NodeMCU 0.9, zależnie od wersji).
   - W Narzędzia -> **Flash Size** upewnij się, że masz przydzielone miejsce na system plików, np. ustawione na **4MB (FS:2MB OTA:~1019KB)** lub podobnie z `FS` (Filesystem). Jest to niezbędne, aby działał system LittleFS.

Następnie podmień u góry kodu zmienne:
- `WIFI_SSID`, `WIFI_PASS`
- `API_URL_PRIMARY`, `API_URL_SECONDARY`, `API_SECRET`, `HEALTHCHECKS_URL`

Skonfiguruj, kliknij **Wgraj** i system powinien ożyć!
