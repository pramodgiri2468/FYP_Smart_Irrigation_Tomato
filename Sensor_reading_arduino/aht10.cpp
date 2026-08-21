#include <Arduino.h>
#include <DHT.h>

// ===== DHT11 PIN =====
// Change to 41 if your DATA wire is connected to GPIO41
#define DHT_PIN   4
#define DHT_TYPE  DHT11

DHT dht(DHT_PIN, DHT_TYPE);

// Global sensor values (used by main .ino)
float temperature = 0.0;
float humidity = 0.0;
float pressure = 0.0;   // Not used with DHT11

// Status flags
bool lastDHTOK = false;

void initSensors() {
    Serial.println("Initializing DHT11...");

    dht.begin();
    delay(1000);

    Serial.print("DHT11 DATA Pin: ");
    Serial.println(DHT_PIN);

    Serial.println("DHT11 initialized.");
}

bool readSensors() {
    humidity = dht.readHumidity();
    temperature = dht.readTemperature();

    if (isnan(humidity) || isnan(temperature)) {
        Serial.println("Failed to read from DHT11!");
        lastDHTOK = false;
        return false;
    }

    pressure = 0.0;   // DHT11 doesn't measure pressure

    lastDHTOK = true;
    return true;
}