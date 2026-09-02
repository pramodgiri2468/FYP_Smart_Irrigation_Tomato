#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_BMP280.h>

// ESP32-S3 default I2C. Change if your SDA/SCL wires use other pins.
#define BMP_SDA 8
#define BMP_SCL 9

Adafruit_BMP280 bmp;

float pressure = 0.0;
bool lastBmpOK = false;

void initBmp280() {
    Serial.println("Initializing BMP280...");
    Wire.begin(BMP_SDA, BMP_SCL);

    if (bmp.begin(0x76) || bmp.begin(0x77)) {
        bmp.setSampling(
            Adafruit_BMP280::MODE_NORMAL,
            Adafruit_BMP280::SAMPLING_X2,
            Adafruit_BMP280::SAMPLING_X16,
            Adafruit_BMP280::FILTER_X16,
            Adafruit_BMP280::STANDBY_MS_500
        );
        lastBmpOK = true;
        Serial.print("BMP280 SDA=");
        Serial.print(BMP_SDA);
        Serial.print(" SCL=");
        Serial.println(BMP_SCL);
        return;
    }

    lastBmpOK = false;
    pressure = 0.0;
    Serial.println("BMP280 not found — API will use Kathmandu mean pressure.");
}

bool readPressure() {
    if (!lastBmpOK) {
        pressure = 0.0;
        return false;
    }

    float hpa = bmp.readPressure() / 100.0F;
    if (isnan(hpa) || hpa < 300.0F || hpa > 1100.0F) {
        Serial.println("BMP280 read failed.");
        pressure = 0.0;
        return false;
    }

    pressure = hpa;
    return true;
}
