#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include "tomato_thresholds.h"

// ===== WIFI CONFIG =====
#define WIFI_SSID   "pramodwifi246_2"
#define WIFI_PASS   "G9#fX2@kLp!7RmQz"

// Optional historical log (system design layer 4). Live control uses FastAPI.
#define ENABLE_GOOGLE_SHEETS 1
#define SCRIPT_URL  "https://script.google.com/macros/s/AKfycbw9etTizWnSERy0UmpoW_jPVl0iasuGZTRrtUKrDxTUkHywvrx_hKU_m_zm7xmY-fw/exec"

// This Mac's LAN IP (ipconfig getifaddr en0). Same Wi-Fi as the ESP32.
#define ENABLE_FASTAPI 1
#define API_HOST       "192.168.1.79"
#define API_PORT       8000

// Used when BMP280 is missing (Kathmandu greenhouse site, hPa)
const float SITE_PRESSURE_HPA = 865.0f;

void initSensors();
bool readSensors();
void initBmp280();
bool readPressure();
void initSoilMoisture();
float readSoilMoisture();
void setRelay(bool on);
void updateTomatoRelay(float t, float h, float soil, bool climateOk);

bool ensureWiFiConnected();
bool sendToGoogle(float t, float h, float p, float s, int relay, int waterNeeded);
bool requestIrrigationDecision(float t, float h, float p, float s, bool* irrigate);
bool parseWaterNeeded(const String& body, bool* irrigate);
void printTomatoStatus(float t, float h, float soil, bool climateOk);
const char* rangeStatus(float value, float minV, float maxV);
float currentPressureHpa();
void resetSheetAverages();
void resetPredictAverages();

extern float temperature;
extern float humidity;
extern float pressure;
extern bool lastDHTOK;
extern bool lastBmpOK;

extern float soilMoisture;
extern int soilRaw;
extern int soilDigital;
extern int relayStatus;

unsigned long startMillis = 0;
unsigned long lastSampleMillis = 0;
unsigned long lastSheetMillis = 0;
unsigned long lastPredictMillis = 0;
unsigned long lastPredictAttemptMillis = 0;

float sheetTempSum = 0, sheetHumSum = 0, sheetSoilSum = 0, sheetPressureSum = 0;
uint32_t sheetCount = 0, sheetPressureCount = 0;
float predTempSum = 0, predHumSum = 0, predSoilSum = 0, predPressureSum = 0;
uint32_t predCount = 0, predPressureCount = 0;
int lastWaterNeeded = 0;
bool firstSheetDone = false;

const unsigned long SAMPLE_INTERVAL = 2000;
const unsigned long FIRST_SHEET_DELAY = 20UL * 1000UL;
const unsigned long SHEET_INTERVAL = 15UL * 60UL * 1000UL;
const unsigned long PREDICT_INTERVAL = 15000;
const unsigned long PREDICT_RETRY_INTERVAL = 5000;
const unsigned long WIFI_CONNECT_TIMEOUT = 20000;

void resetSheetAverages() {
    sheetTempSum = sheetHumSum = sheetSoilSum = sheetPressureSum = 0;
    sheetCount = sheetPressureCount = 0;
}

void resetPredictAverages() {
    predTempSum = predHumSum = predSoilSum = predPressureSum = 0;
    predCount = predPressureCount = 0;
}

float currentPressureHpa() {
    if (lastBmpOK && pressure > 0) {
        return pressure;
    }
    return SITE_PRESSURE_HPA;
}

bool ensureWiFiConnected() {
    if (WiFi.status() == WL_CONNECTED) {
        return true;
    }

    Serial.print("Connecting to WiFi");
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);

    unsigned long connectStart = millis();
    while ((WiFi.status() != WL_CONNECTED) &&
           ((millis() - connectStart) < WIFI_CONNECT_TIMEOUT)) {
        delay(500);
        Serial.print(".");
    }
    Serial.println();

    if (WiFi.status() == WL_CONNECTED) {
        Serial.print("WiFi Connected! IP ");
        Serial.println(WiFi.localIP());
        return true;
    }

    Serial.println("WiFi connection failed.");
    return false;
}

void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println();
    Serial.println("==============================");
    Serial.println("Smart Irrigation Tomato");
    Serial.println("Sensing -> ESP32 -> Wi-Fi -> FastAPI XGBoost -> pump");
    Serial.println("==============================");

    initSensors();
    initBmp280();
    initSoilMoisture();

    WiFi.setAutoReconnect(true);
    ensureWiFiConnected();

    unsigned long now = millis();
    startMillis = now;
    lastSampleMillis = now;
    lastSheetMillis = now;
    lastPredictMillis = 0;
    lastPredictAttemptMillis = 0;
    resetSheetAverages();
    resetPredictAverages();

    Serial.println("System Started.");
}

void loop() {
    unsigned long now = millis();

    if (now - lastSampleMillis >= SAMPLE_INTERVAL) {
        lastSampleMillis = now;

        readSensors();
        readPressure();
        float soil = readSoilMoisture();
        float pNow = currentPressureHpa();

        if (lastDHTOK) {
            sheetTempSum += temperature;
            sheetHumSum += humidity;
            sheetSoilSum += soil;
            sheetCount++;
            predTempSum += temperature;
            predHumSum += humidity;
            predSoilSum += soil;
            predCount++;
        }
        if (lastBmpOK && pressure > 0) {
            sheetPressureSum += pressure;
            sheetPressureCount++;
            predPressureSum += pressure;
            predPressureCount++;
        }

        float tSend = lastDHTOK && predCount > 0 ? (predTempSum / predCount) : temperature;
        float hSend = lastDHTOK && predCount > 0 ? (predHumSum / predCount) : humidity;
        float sSend = predCount > 0 ? (predSoilSum / predCount) : soil;
        float pSend = predPressureCount > 0 ? (predPressureSum / predPressureCount) : pNow;

#if ENABLE_FASTAPI
        bool apiOk = false;
        bool due = (lastPredictMillis == 0) ||
                   ((now - lastPredictMillis) >= PREDICT_INTERVAL);
        if (lastDHTOK && due &&
            ((now - lastPredictAttemptMillis) >= PREDICT_RETRY_INTERVAL)) {
            lastPredictAttemptMillis = now;
            bool irrigate = false;
            if (requestIrrigationDecision(tSend, hSend, pSend, sSend, &irrigate)) {
                lastPredictMillis = now;
                apiOk = true;
                lastWaterNeeded = irrigate ? 1 : 0;
                resetPredictAverages();
                setRelay(irrigate);
                Serial.print("ML decision: pump ");
                Serial.println(irrigate ? "ON" : "OFF");
            } else {
                Serial.println("FastAPI unreachable — local tomato thresholds.");
            }
        } else if (lastPredictMillis != 0 &&
                   ((now - lastPredictMillis) < (PREDICT_INTERVAL * 3))) {
            apiOk = true;
        }
        if (!apiOk) {
            updateTomatoRelay(temperature, humidity, soil, lastDHTOK);
            lastWaterNeeded = relayStatus;
        }
#else
        updateTomatoRelay(temperature, humidity, soil, lastDHTOK);
        lastWaterNeeded = relayStatus;
#endif

        Serial.println("--------------------------------");
        if (lastDHTOK) {
            Serial.print("Temperature : ");
            Serial.print(temperature);
            Serial.println(" C");
            Serial.print("Humidity    : ");
            Serial.print(humidity);
            Serial.println(" %");
        } else {
            Serial.println("DHT11 Read Failed");
        }
        if (lastBmpOK && pressure > 0) {
            Serial.print("Pressure    : ");
            Serial.print(pressure);
            Serial.println(" hPa");
        } else {
            Serial.print("Pressure    : ");
            Serial.print(SITE_PRESSURE_HPA, 0);
            Serial.println(" hPa (site)");
        }
        Serial.print("Soil Moist. : ");
        Serial.print(soil);
        Serial.println(" %");
        Serial.print("Relay       : ");
        Serial.println(relayStatus ? "ON" : "OFF");
        printTomatoStatus(temperature, humidity, soil, lastDHTOK);
        Serial.println("--------------------------------");
    }

#if ENABLE_GOOGLE_SHEETS
    bool sheetDue = (!firstSheetDone && sheetCount > 0 &&
                     (now - startMillis) >= FIRST_SHEET_DELAY) ||
                    ((now - lastSheetMillis) >= SHEET_INTERVAL);
    if (sheetDue && sheetCount > 0) {
        float avgTemp = sheetTempSum / sheetCount;
        float avgHum = sheetHumSum / sheetCount;
        float avgSoil = sheetSoilSum / sheetCount;
        float avgP = sheetPressureCount > 0 ? (sheetPressureSum / sheetPressureCount)
                                           : currentPressureHpa();

        Serial.println("======= Cloud layer: Google Sheets average =======");
        if (sendToGoogle(avgTemp, avgHum, avgP, avgSoil, relayStatus, lastWaterNeeded)) {
            firstSheetDone = true;
            lastSheetMillis = now;
            resetSheetAverages();
        }
    }
#endif
}

const char* rangeStatus(float value, float minV, float maxV) {
    if (value < minV) {
        return "LOW";
    }
    if (value > maxV) {
        return "HIGH";
    }
    return "OK";
}

void printTomatoStatus(float t, float h, float soil, bool climateOk) {
    Serial.println("Tomato greenhouse status:");
    if (climateOk) {
        Serial.print("  Temp range : ");
        Serial.println(rangeStatus(t, TOMATO_TEMP_MIN, TOMATO_TEMP_MAX));
        Serial.print("  Hum range  : ");
        Serial.println(rangeStatus(h, TOMATO_HUM_MIN, TOMATO_HUM_MAX));
    } else {
        Serial.println("  Temp/Hum   : N/A");
    }
    Serial.print("  Soil range : ");
    Serial.println(rangeStatus(soil, TOMATO_SOIL_MIN, TOMATO_SOIL_MAX));
}

bool sendToGoogle(float t, float h, float p, float s, int relay, int waterNeeded) {
    if (!ensureWiFiConnected()) {
        return false;
    }

    if (String(SCRIPT_URL).indexOf("PASTE_NEW") >= 0) {
        Serial.println("Sheets skipped: paste SCRIPT_URL.");
        return false;
    }

    String url = String(SCRIPT_URL);
    url += "?temperature=" + String(t, 2);
    url += "&humidity=" + String(h, 2);
    url += "&pressure=" + String(p, 2);
    url += "&soilMoisture=" + String(s, 2);
    url += "&relay=" + String(relay);
    url += "&water_needed=" + String(waterNeeded);
    url += "&temp_min=" + String(TOMATO_TEMP_MIN, 1);
    url += "&temp_max=" + String(TOMATO_TEMP_MAX, 1);
    url += "&hum_min=" + String(TOMATO_HUM_MIN, 1);
    url += "&hum_max=" + String(TOMATO_HUM_MAX, 1);
    url += "&soil_min=" + String(TOMATO_SOIL_MIN, 1);
    url += "&soil_max=" + String(TOMATO_SOIL_MAX, 1);
    url += "&temp_status=" + String(rangeStatus(t, TOMATO_TEMP_MIN, TOMATO_TEMP_MAX));
    url += "&hum_status=" + String(rangeStatus(h, TOMATO_HUM_MIN, TOMATO_HUM_MAX));
    url += "&soil_status=" + String(rangeStatus(s, TOMATO_SOIL_MIN, TOMATO_SOIL_MAX));
    url += "&device_id=esp32-irrigation";
    url += "&crop=tomato";

    Serial.println("Sending averaged row to Google Sheets");

    WiFiClientSecure client;
    client.setInsecure();

    HTTPClient http;
    http.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);
    http.setTimeout(15000);
    http.begin(client, url);

    int httpCode = http.GET();
    Serial.print("Sheets HTTP ");
    Serial.println(httpCode);
    bool ok = (httpCode == 200 || httpCode == 302);
    http.end();
    return ok;
}

bool parseWaterNeeded(const String& body, bool* irrigate) {
    int idx = body.indexOf("\"water_needed\"");
    if (idx >= 0) {
        int colon = body.indexOf(':', idx);
        if (colon >= 0) {
            String rest = body.substring(colon + 1);
            rest.trim();
            *irrigate = rest.startsWith("1");
            return true;
        }
    }

    idx = body.indexOf("\"irrigate\"");
    if (idx >= 0) {
        int colon = body.indexOf(':', idx);
        if (colon >= 0) {
            String rest = body.substring(colon + 1);
            rest.trim();
            *irrigate = rest.startsWith("true") || rest.startsWith("1");
            return true;
        }
    }
    return false;
}

bool requestIrrigationDecision(float t, float h, float p, float s, bool* irrigate) {
    if (!ensureWiFiConnected()) {
        Serial.println("WiFi unavailable, cannot call /predict.");
        return false;
    }

    String url = String("http://") + API_HOST + ":" + String(API_PORT) + "/predict";
    String payload = "{";
    payload += "\"temperature\":" + String(t, 2) + ",";
    payload += "\"humidity\":" + String(h, 2) + ",";
    payload += "\"pressure\":" + String(p, 2) + ",";
    payload += "\"soilMoisture\":" + String(s, 2) + ",";
    payload += "\"device_id\":\"esp32-irrigation\"";
    payload += "}";

    Serial.println("POST /predict");
    Serial.println(payload);

    HTTPClient http;
    http.begin(url);
    http.addHeader("Content-Type", "application/json");
    http.setTimeout(8000);

    int httpCode = http.POST(payload);
    String body = http.getString();
    http.end();

    Serial.print("HTTP ");
    Serial.println(httpCode);
    Serial.println(body);

    if (httpCode != 200) {
        return false;
    }
    return parseWaterNeeded(body, irrigate);
}
