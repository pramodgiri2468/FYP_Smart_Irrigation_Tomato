#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>

// Arduino Library Manager: "DHT sensor library", "Adafruit BMP280 Library",
// "Adafruit Unified Sensor".

// ===== WIFI CONFIG =====
#define WIFI_SSID   "pramodwifi246_2"
#define WIFI_PASS   "G9#fX2@kLp!7RmQz"

// This Mac's LAN IP (System Settings → Network, or: ipconfig getifaddr en0).
// Must be the same Wi-Fi as the ESP32. Docker / uvicorn listens on port 8000.
#define API_HOST    "192.168.1.79"
#define API_PORT    8000

// Optional extra log. Live decisions go to FastAPI (CSV + dashboard).
#define ENABLE_GOOGLE_SHEETS 0
#if ENABLE_GOOGLE_SHEETS
#define SCRIPT_URL  "https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec"
#endif

void initSensors();
bool readSensors();
void initBmp280();
bool readPressure();
void initSoilMoisture();
float readSoilMoisture();
void setRelay(bool on);

bool ensureWiFiConnected();
bool requestIrrigationDecision(float t, float h, float p, float s, bool* irrigate);
bool parseWaterNeeded(const String& body, bool* irrigate);

extern float temperature;
extern float humidity;
extern float pressure;
extern bool lastDHTOK;
extern bool lastBmpOK;

extern float soilMoisture;
extern int soilRaw;
extern int soilDigital;
extern bool relayState;

unsigned long lastSampleMillis = 0;
unsigned long lastPredictMillis = 0;
unsigned long lastPredictAttemptMillis = 0;

const unsigned long SAMPLE_INTERVAL = 2000;
const unsigned long PREDICT_INTERVAL = 15000;
const unsigned long PREDICT_RETRY_INTERVAL = 5000;
const unsigned long WIFI_CONNECT_TIMEOUT = 20000;

bool ensureWiFiConnected() {
    if (WiFi.status() == WL_CONNECTED) {
        return true;
    }

    Serial.println();
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
        Serial.println("WiFi Connected!");
        Serial.print("IP Address: ");
        Serial.println(WiFi.localIP());
        return true;
    }

    Serial.println("WiFi connection failed.");
    return false;
}

void applyFallbackRelay(float soil) {
    bool on = (soil <= 0.0);
    setRelay(on);
    Serial.print("API unreachable — fallback relay ");
    Serial.println(on ? "ON (dry ADC floor)" : "OFF");
}

void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println();
    Serial.println("==============================");
    Serial.println("Smart Irrigation Tomato");
    Serial.println("ESP32 -> FastAPI /predict");
    Serial.println("==============================");

    initSensors();
    initBmp280();
    initSoilMoisture();

    WiFi.setAutoReconnect(true);
    ensureWiFiConnected();

    unsigned long now = millis();
    lastSampleMillis = now;
    lastPredictMillis = 0;
    lastPredictAttemptMillis = 0;

    Serial.println("System Started.");
}

void loop() {
    unsigned long now = millis();

    if (now - lastSampleMillis >= SAMPLE_INTERVAL) {
        lastSampleMillis = now;

        readSensors();
        readPressure();
        float soil = readSoilMoisture();

        Serial.println("--------------------------------");
        if (lastDHTOK) {
            Serial.print("Temperature : ");
            Serial.print(temperature);
            Serial.println(" C");
            Serial.print("Humidity    : ");
            Serial.print(humidity);
            Serial.println(" %");
        } else {
            Serial.println("DHT11 read failed");
        }
        if (lastBmpOK && pressure > 0) {
            Serial.print("Pressure    : ");
            Serial.print(pressure);
            Serial.println(" hPa");
        } else {
            Serial.println("Pressure    : (API prior)");
        }
        Serial.print("Soil Moist. : ");
        Serial.print(soil);
        Serial.println(" %");
        Serial.print("Relay       : ");
        Serial.println(relayState ? "ON" : "OFF");
        Serial.println("--------------------------------");
    }

    bool due = (lastPredictMillis == 0) ||
               ((now - lastPredictMillis) >= PREDICT_INTERVAL);
    if (due && ((now - lastPredictAttemptMillis) >= PREDICT_RETRY_INTERVAL)) {
        lastPredictAttemptMillis = now;

        float t = lastDHTOK ? temperature : 0.0;
        float h = lastDHTOK ? humidity : 0.0;
        float p = pressure;
        float s = soilMoisture;
        bool irrigate = false;

        if (requestIrrigationDecision(t, h, p, s, &irrigate)) {
            lastPredictMillis = now;
            setRelay(irrigate);
            Serial.print("ML decision: pump ");
            Serial.println(irrigate ? "ON" : "OFF");
        } else {
            applyFallbackRelay(s);
        }
    }
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

    idx = body.indexOf("\"relayStatus\"");
    if (idx >= 0) {
        *irrigate = body.indexOf("\"ON\"", idx) >= 0;
        return true;
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

#if ENABLE_GOOGLE_SHEETS
bool sendToGoogle(float t, float h, float p, float s, bool relayOn) {
    if (!ensureWiFiConnected()) {
        return false;
    }

    HTTPClient http;
    http.begin(SCRIPT_URL);
    http.addHeader("Content-Type", "application/json");
    http.setTimeout(15000);
    http.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);

    String payload = "{";
    payload += "\"temperature\":" + String(t, 2) + ",";
    payload += "\"humidity\":" + String(h, 2) + ",";
    payload += "\"pressure\":" + String(p, 2) + ",";
    payload += "\"soilMoisture\":" + String(s, 2) + ",";
    payload += "\"relayStatus\":\"" + String(relayOn ? "ON" : "OFF") + "\",";
    payload += "\"targetValue\":" + String(relayOn ? 100.0 : 0.0, 2) + ",";
    payload += "\"device_id\":\"esp32-irrigation\"";
    payload += "}";

    int httpCode = http.POST(payload);
    http.end();
    return (httpCode == 200 || httpCode == 302);
}
#endif
