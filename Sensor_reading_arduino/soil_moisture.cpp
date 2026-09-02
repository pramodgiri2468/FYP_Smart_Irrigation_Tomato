#include <Arduino.h>

#define SOIL_AO_PIN 20
#define SOIL_DO_PIN 36
#define RELAY_PIN 1

#define NUM_SAMPLES 20
#define SAMPLE_DELAY 1

static int DRY_SOIL = 3800;
static int WET_SOIL = 1400;

float soilMoisture = 0.0;
int soilRaw = 0;
int soilDigital = 0;
bool relayState = false;

void initSoilMoisture() {
    pinMode(SOIL_AO_PIN, INPUT);
    pinMode(SOIL_DO_PIN, INPUT);

    // Relay is ACTIVE LOW: LOW = ON, HIGH = OFF
    digitalWrite(RELAY_PIN, HIGH);
    pinMode(RELAY_PIN, OUTPUT);
    digitalWrite(RELAY_PIN, HIGH);
    relayState = false;

    analogReadResolution(12);
    analogSetPinAttenuation(SOIL_AO_PIN, ADC_11db);

    Serial.println("Soil moisture sensor initialized.");
    Serial.print("Soil AO pin: ");
    Serial.println(SOIL_AO_PIN);
    Serial.print("Soil DO pin: ");
    Serial.println(SOIL_DO_PIN);
}

void setRelay(bool on) {
    digitalWrite(RELAY_PIN, on ? LOW : HIGH);
    relayState = on;
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
    return soilMoisture;
}
