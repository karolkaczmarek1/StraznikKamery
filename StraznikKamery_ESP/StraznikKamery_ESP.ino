#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include <LittleFS.h>
#include <ESP8266Ping.h>
#include <NTPClient.h>
#include <WiFiUdp.h>

// --- KONFIGURACJA SIECI ---
const char* WIFI_SSID = "TWOJA_SIEC_WIFI";
const char* WIFI_PASS = "TWOJE_HASLO_WIFI";

// --- KONFIGURACJA SERWERA API ---
const char* API_URL_PRIMARY = "http://twoj_adres_serwera:port/update";
const char* API_URL_SECONDARY = "http://zapasowy_adres_serwera:port/update";
const char* API_SECRET = "TWOJ_TAJNY_KLUCZ_API";

// --- KONFIGURACJA HEALTHCHECKS ---
const char* HEALTHCHECKS_URL = "https://hc-ping.com/TWOJ_SLUG_ESP";

// --- PROGI ALERTÓW ---
const int PING_FAIL_THRESHOLD = 3;  // Ile nieudanych pingów pod rząd to alert "Brak Internetu"
const int PING_SUCCESS_THRESHOLD = 3; // Ile udanych pod rząd to powrót internetu

// --- INTERWAŁY (w milisekundach) ---
const unsigned long WIFI_CHECK_INTERVAL = 5000;
const unsigned long PING_CHECK_INTERVAL = 30000;
const unsigned long SERVER_SEND_INTERVAL = 60000;
const unsigned long HC_SEND_INTERVAL = 300000;

// --- ZMIENNE STANOWE ---
bool isWifiConnected = false;
bool isInternetOk = false;
int failedPings = 0;
int successfulPings = 0;
long lastPingTimeMs = 0;

unsigned long lastWifiCheck = 0;
unsigned long lastPingCheck = 0;
unsigned long lastServerSend = 0;
unsigned long lastHcSend = 0;

// --- NTP ---
WiFiUDP ntpUDP;
NTPClient timeClient(ntpUDP, "pool.ntp.org", 0, 60000); // Czas UTC

void addAlertToFS(String type, String details) {
    String filename = "/alerts.json";
    DynamicJsonDocument doc(2048);
    
    if (LittleFS.exists(filename)) {
        File file = LittleFS.open(filename, "r");
        if (file) {
            DeserializationError error = deserializeJson(doc, file);
            if (error) {
                Serial.println("Failed to read alerts, creating new.");
                doc.to<JsonArray>();
            }
            file.close();
        }
    } else {
        doc.to<JsonArray>();
    }

    JsonObject newAlert = doc.createNestedObject();
    newAlert["type"] = type;
    newAlert["time"] = timeClient.isTimeSet() ? timeClient.getFormattedTime() : "NotSync";
    newAlert["details"] = details;

    File file = LittleFS.open(filename, "w");
    if (file) {
        serializeJson(doc, file);
        file.close();
        Serial.println("Alert zapisany: " + type);
    }
}

void clearAlertsFromFS() {
    LittleFS.remove("/alerts.json");
    Serial.println("Alerty wyczyszczone z pamięci.");
}

void setup() {
    Serial.begin(115200);
    delay(1000);
    
    if (!LittleFS.begin()) {
        Serial.println("Błąd montowania LittleFS!");
    }

    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    
    addAlertToFS("SYSTEM_BOOT", "Uruchomienie ESP8266");
}

bool pingServers() {
    const char* servers[] = {"8.8.8.8", "1.1.1.1"};
    for (int i = 0; i < 2; i++) {
        if (Ping.ping(servers[i], 1)) {
            lastPingTimeMs = Ping.averageTime();
            return true;
        }
    }
    return false;
}

void sendToServer() {
    if (WiFi.status() != WL_CONNECTED) return;

    DynamicJsonDocument doc(4096);
    JsonObject status = doc.createNestedObject("status");
    status["wifi_ssid"] = WiFi.SSID();
    status["wifi_rssi"] = WiFi.RSSI();
    status["internet_ok"] = isInternetOk;
    status["ping_time_ms"] = lastPingTimeMs;
    status["uptime_s"] = millis() / 1000;

    if (LittleFS.exists("/alerts.json")) {
        File file = LittleFS.open("/alerts.json", "r");
        if (file) {
            JsonArray alerts = doc.createNestedArray("alerts");
            DynamicJsonDocument tempDoc(2048);
            if (!deserializeJson(tempDoc, file)) {
                for (JsonObject alert : tempDoc.as<JsonArray>()) {
                    alerts.add(alert);
                }
            }
            file.close();
        }
    }

    String payload;
    serializeJson(doc, payload);

    bool success = false;
    
    // Próba Primary (HTTP)
    WiFiClient client;
    HTTPClient http;
    http.begin(client, API_URL_PRIMARY);
    http.addHeader("Content-Type", "application/json");
    http.addHeader("Authorization", String("Bearer ") + API_SECRET);
    
    int httpResponseCode = http.POST(payload);
    if (httpResponseCode == 200) {
        success = true;
        Serial.println("Wysłano do Primary API.");
    } else {
        Serial.printf("Primary API błąd: %d\n", httpResponseCode);
        http.end();
        
        // Próba Secondary (HTTP)
        http.begin(client, API_URL_SECONDARY);
        http.addHeader("Content-Type", "application/json");
        http.addHeader("Authorization", String("Bearer ") + API_SECRET);
        httpResponseCode = http.POST(payload);
        if (httpResponseCode == 200) {
            success = true;
            Serial.println("Wysłano do Secondary API.");
        } else {
            Serial.printf("Secondary API błąd: %d\n", httpResponseCode);
        }
    }
    http.end();

    if (success) {
        clearAlertsFromFS();
    }
}

void pingHealthchecks() {
    if (!isInternetOk) return;
    WiFiClientSecure clientSec;
    clientSec.setInsecure();
    HTTPClient http;
    http.begin(clientSec, HEALTHCHECKS_URL);
    int httpCode = http.GET();
    http.end();
    Serial.printf("Healthchecks.io status: %d\n", httpCode);
}

void loop() {
    unsigned long currentMillis = millis();

    // 1. Sprawdzanie Wi-Fi
    if (currentMillis - lastWifiCheck >= WIFI_CHECK_INTERVAL) {
        lastWifiCheck = currentMillis;
        bool currentWifi = (WiFi.status() == WL_CONNECTED);
        
        if (currentWifi && !isWifiConnected) {
            isWifiConnected = true;
            addAlertToFS("WIFI_CONNECTED", "Połączono z " + WiFi.SSID());
            timeClient.begin(); // Uruchom NTP po połączeniu
        } else if (!currentWifi && isWifiConnected) {
            isWifiConnected = false;
            isInternetOk = false;
            addAlertToFS("WIFI_DISCONNECTED", "Rozłączono z siecią");
        }
        
        if (isWifiConnected) {
            timeClient.update();
        }
    }

    // 2. Sprawdzanie Internetu
    if (currentMillis - lastPingCheck >= PING_CHECK_INTERVAL) {
        lastPingCheck = currentMillis;
        if (isWifiConnected) {
            bool pingOk = pingServers();
            if (pingOk) {
                successfulPings++;
                failedPings = 0;
                if (successfulPings >= PING_SUCCESS_THRESHOLD && !isInternetOk) {
                    isInternetOk = true;
                    addAlertToFS("INTERNET_RESTORED", "Połączenie z internetem przywrócone");
                }
            } else {
                failedPings++;
                successfulPings = 0;
                if (failedPings >= PING_FAIL_THRESHOLD && isInternetOk) {
                    isInternetOk = false;
                    addAlertToFS("INTERNET_LOST", "Brak odpowiedzi ping");
                }
            }
        }
    }

    // 3. Wysyłanie do VPS
    if (currentMillis - lastServerSend >= SERVER_SEND_INTERVAL) {
        lastServerSend = currentMillis;
        sendToServer();
    }

    // 4. Wysyłanie do Healthchecks.io
    if (currentMillis - lastHcSend >= HC_SEND_INTERVAL) {
        lastHcSend = currentMillis;
        pingHealthchecks();
    }
}
