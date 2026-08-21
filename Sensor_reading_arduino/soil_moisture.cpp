#include <Arduino.h>

// Soil sensor pins
#define SOIL_AO_PIN 20
#define SOIL_DO_PIN 36

// Relay pin
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

// Relay status (true = ON, false = OFF)
bool relayState = false;

void initSoilMoisture() {

    pinMode(SOIL_AO_PIN, INPUT);
    pinMode(SOIL_DO_PIN, INPUT);

    // Relay is ACTIVE LOW  ->  LOW = ON, HIGH = OFF
    // Drive HIGH before setting OUTPUT so the relay
    // does not click ON for a moment during boot
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

    // Relay Control
    // ON as soon as the soil reaches the dry threshold
    bool trigger = (soilMoisture <= 0.0);

    if (trigger) {
        digitalWrite(RELAY_PIN, LOW);      // LOW = Relay ON
        relayState = true;
        Serial.println("Relay ON (Dry Soil)");
    } else {
        digitalWrite(RELAY_PIN, HIGH);     // HIGH = Relay OFF
        relayState = false;
        Serial.println("Relay OFF");
    }

    return soilMoisture;
}
