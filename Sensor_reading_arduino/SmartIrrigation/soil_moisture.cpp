#include <Arduino.h>
#include "tomato_thresholds.h"

// Soil sensor pins
#define SOIL_AO_PIN 20
#define SOIL_DO_PIN 36

// Relay pin (active LOW module: LOW = ON, HIGH = OFF)
#define RELAY_PIN 1

#define NUM_SAMPLES 20
#define SAMPLE_DELAY 1

// Calibration values
static int DRY_SOIL = 3800;
static int WET_SOIL = 1400;

// Global variables
float soilMoisture = 0.0;
int soilRaw = 0;
int soilDigital = 0;
int relayStatus = 0;  // 1 = ON (pumping), 0 = OFF

void setRelay(bool on) {

    if (on) {
        digitalWrite(RELAY_PIN, LOW);
        relayStatus = 1;
    } else {
        digitalWrite(RELAY_PIN, HIGH);
        relayStatus = 0;
    }
}

void initSoilMoisture() {

    pinMode(SOIL_AO_PIN, INPUT);
    pinMode(SOIL_DO_PIN, INPUT);

    pinMode(RELAY_PIN, OUTPUT);

    digitalWrite(RELAY_PIN, HIGH);
    relayStatus = 0;

    analogReadResolution(12);
    analogSetPinAttenuation(SOIL_AO_PIN, ADC_11db);

    Serial.println("Soil moisture sensor initialized.");
    Serial.print("Soil AO pin: ");
    Serial.println(SOIL_AO_PIN);
    Serial.print("Soil DO pin: ");
    Serial.println(SOIL_DO_PIN);

    Serial.println("Tomato greenhouse thresholds:");
    Serial.print("  Temp ");
    Serial.print(TOMATO_TEMP_MIN);
    Serial.print("-");
    Serial.print(TOMATO_TEMP_MAX);
    Serial.println(" C");
    Serial.print("  Humidity ");
    Serial.print(TOMATO_HUM_MIN);
    Serial.print("-");
    Serial.print(TOMATO_HUM_MAX);
    Serial.println(" %");
    Serial.print("  Soil ");
    Serial.print(TOMATO_SOIL_MIN);
    Serial.print("-");
    Serial.print(TOMATO_SOIL_MAX);
    Serial.println(" %");
}

int readSoilRaw() {

    long sum = 0;

    for (int i = 0; i < NUM_SAMPLES; i++) {
        sum += analogRead(SOIL_AO_PIN);
        delay(SAMPLE_DELAY);
    }

    soilRaw = sum / NUM_SAMPLES;
    return soilRaw;
}

float readSoilMoisture() {

    int raw = readSoilRaw();
    soilDigital = digitalRead(SOIL_DO_PIN);

    float percent = 100.0 * (DRY_SOIL - raw) / (DRY_SOIL - WET_SOIL);
    percent = constrain(percent, 0.0, 100.0);

    soilMoisture = percent;
    if (percent <= 0.0) {
        Serial.println("Soil 0% — check probe wiring and DRY_SOIL / WET_SOIL calibration.");
    }
    return soilMoisture;
}

void updateTomatoRelay(float t, float h, float soil, bool climateOk) {

    bool needWater;

    if (soil < TOMATO_SOIL_MIN) {
        needWater = true;
    } else if (soil > TOMATO_SOIL_MAX) {
        needWater = false;
    } else {
        needWater = (relayStatus == 1);
    }

    if (climateOk) {
        if (t < TOMATO_TEMP_MIN) {
            needWater = false;
        }
        if (h > TOMATO_HUM_MAX && soil >= TOMATO_SOIL_MIN) {
            needWater = false;
        }
    }

    setRelay(needWater);

    Serial.print("Relay        : ");
    Serial.print(relayStatus);
    Serial.println(relayStatus ? " (ON)" : " (OFF)");
}
