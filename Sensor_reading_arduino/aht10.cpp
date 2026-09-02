#include <Arduino.h>
#include <DHT.h>

// Change to 41 if your DATA wire is connected to GPIO41
#define DHT_PIN   4
#define DHT_TYPE  DHT11

DHT dht(DHT_PIN, DHT_TYPE);

float temperature = 0.0;
float humidity = 0.0;
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

    lastDHTOK = true;
    return true;
}
