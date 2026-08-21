#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>

// ===== WIFI CONFIG =====
#define WIFI_SSID   "pramodwifi246_2"
#define WIFI_PASS   "G9#fX2@kLp!7RmQz"

// ===== GOOGLE APPS SCRIPT URL =====
#define SCRIPT_URL  "https://script.google.com/macros/s/AKfycbxBRhGZF-XKXWNj4brEHefVFMneYQaY_VIjGHpFJPlwk_8qUn2e1KQVcvw-sJY4FqFK/exec"

// ===== Function declarations =====
void initSensors();
bool readSensors();

void initSoilMoisture();
float readSoilMoisture();

bool ensureWiFiConnected();
bool sendToGoogle(float t, float h, float p, float s, bool relayOn);
void resetAverages();

// ===== Globals from DHT =====
extern float temperature;
extern float humidity;
extern float pressure;
extern bool lastDHTOK;

// ===== Globals from soil_moisture.cpp =====
extern float soilMoisture;
extern int soilRaw;
extern int soilDigital;
extern bool relayState;

// ===== Averaging variables =====
unsigned long lastSampleMillis = 0;
unsigned long lastSendMillis = 0;
unsigned long lastSendAttemptMillis = 0;

float tempSum = 0;
float humSum  = 0;
float soilSum = 0;
uint32_t sampleCount = 0;

bool relayOnUploadPending = false;
float pendingRelayTemp = 0.0;
float pendingRelayHum = 0.0;
float pendingRelaySoil = 0.0;

// ===== Timing =====
const unsigned long SAMPLE_INTERVAL = 2000;
const unsigned long SEND_INTERVAL = 15UL * 60UL * 1000UL;
const unsigned long SEND_RETRY_INTERVAL = 5000;
const unsigned long WIFI_CONNECT_TIMEOUT = 20000;
const float TARGET_VALUE_WHEN_RELAY_ON = 100.0;

void resetAverages() {
    tempSum = 0;
    humSum = 0;
    soilSum = 0;
    sampleCount = 0;
}

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

void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println();
    Serial.println("==============================");
    Serial.println("Smart Irrigation Monitoring");
    Serial.println("==============================");

    initSensors();
    initSoilMoisture();

    WiFi.setAutoReconnect(true);
    ensureWiFiConnected();

    unsigned long now = millis();
    lastSampleMillis = now;
    lastSendMillis = now;
    lastSendAttemptMillis = now;

    Serial.println("System Started.");
}

void loop() {
    unsigned long now = millis();

    // ==========================
    // Read sensors every 2 sec
    // ==========================
    if (now - lastSampleMillis >= SAMPLE_INTERVAL) {
        lastSampleMillis = now;

        readSensors();

        bool relayBefore = relayState;
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

        Serial.print("Soil Raw    : ");
        Serial.println(soilRaw);

        Serial.print("Soil Moist. : ");
        Serial.print(soil);
        Serial.println(" %");

        Serial.print("Soil DO     : ");
        Serial.println(soilDigital ? "HIGH" : "LOW");

        Serial.print("Relay       : ");
        Serial.println(relayState ? "ON" : "OFF");

        Serial.println("--------------------------------");

        if (lastDHTOK) {
            tempSum += temperature;
            humSum += humidity;
            soilSum += soil;
            sampleCount++;

            Serial.print("Sample Count: ");
            Serial.println(sampleCount);
        }

        // ==========================
        // Relay just turned ON -> queue/send immediately
        // ==========================
        if (relayState && !relayBefore) {
            Serial.println();
            Serial.println("======= Relay Turned ON =======");
            Serial.println("Sending data immediately...");

            pendingRelayTemp = lastDHTOK ? temperature : 0.0;
            pendingRelayHum = lastDHTOK ? humidity : 0.0;
            pendingRelaySoil = soil;
            relayOnUploadPending = true;
        }

        if (relayOnUploadPending) {
            if (relayState) {
                pendingRelayTemp = lastDHTOK ? temperature : pendingRelayTemp;
                pendingRelayHum = lastDHTOK ? humidity : pendingRelayHum;
                pendingRelaySoil = soil;
            }

            if (sendToGoogle(pendingRelayTemp, pendingRelayHum, 0.0, pendingRelaySoil, true)) {
                relayOnUploadPending = false;
                lastSendMillis = now;
                lastSendAttemptMillis = now;
                resetAverages();
            } else {
                Serial.println("Relay ON upload pending, will retry.");
            }
        }
    }

    // ==========================
    // Upload every 15 minutes
    // ==========================
    if (!relayOnUploadPending &&
        ((now - lastSendMillis) >= SEND_INTERVAL) &&
        ((now - lastSendAttemptMillis) >= SEND_RETRY_INTERVAL)) {

        lastSendAttemptMillis = now;

        float sendTemp = 0.0;
        float sendHum = 0.0;
        float sendSoil = soilMoisture;

        Serial.println();

        if (sampleCount > 0) {
            sendTemp = tempSum / sampleCount;
            sendHum = humSum / sampleCount;
            sendSoil = soilSum / sampleCount;

            Serial.println("======= 15 Minute Average =======");
        } else {
            if (lastDHTOK) {
                sendTemp = temperature;
                sendHum = humidity;
            }

            Serial.println("======= 15 Minute Status Update =======");
            Serial.println("No valid average samples, sending latest relay status.");
        }

        Serial.print("Temperature : ");
        Serial.println(sendTemp);

        Serial.print("Humidity    : ");
        Serial.println(sendHum);

        Serial.print("Soil        : ");
        Serial.println(sendSoil);

        Serial.print("Relay       : ");
        Serial.println(relayState ? "ON" : "OFF");

        if (sendToGoogle(sendTemp, sendHum, 0.0, sendSoil, relayState)) {
            lastSendMillis = now;
            resetAverages();
        } else {
            Serial.println("Timed upload failed, keeping data for retry.");
        }
    }
}

// ===============================
// Google Sheets Upload
// ===============================
bool sendToGoogle(float t, float h, float p, float s, bool relayOn) {
    if (!ensureWiFiConnected()) {
        Serial.println("WiFi unavailable, skipping upload for now.");
        return false;
    }

    HTTPClient http;

    http.begin(SCRIPT_URL);
    http.addHeader("Content-Type", "application/json");
    http.setTimeout(15000);

    // Apps Script replies with a 302 redirect
    http.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);

    String payload = "{";
    payload += "\"temperature\":" + String(t, 2) + ",";
    payload += "\"humidity\":" + String(h, 2) + ",";
    payload += "\"pressure\":" + String(p, 2) + ",";
    payload += "\"soilMoisture\":" + String(s, 2) + ",";
    payload += "\"relayStatus\":\"" + String(relayOn ? "ON" : "OFF") + "\",";
    payload += "\"targetValue\":" + String(relayOn ? TARGET_VALUE_WHEN_RELAY_ON : 0.0, 2) + ",";
    payload += "\"device_id\":\"esp32-irrigation\"";
    payload += "}";

    Serial.println("Sending Payload:");
    Serial.println(payload);

    int httpCode = http.POST(payload);

    Serial.print("HTTP Response Code: ");
    Serial.println(httpCode);

    bool success = (httpCode == 200 || httpCode == 302);

    if (success) {
        Serial.println("Data sent successfully");
    } else {
        Serial.println("Upload failed");
    }

    http.end();
    return success;
}
