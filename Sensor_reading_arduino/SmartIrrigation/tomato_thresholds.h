#ifndef TOMATO_THRESHOLDS_H
#define TOMATO_THRESHOLDS_H

// Greenhouse tomato (Solanum lycopersicum) cultivation ranges
// Day temperature 21–27 °C; fruit coloring fails above ~30 °C.
// Nutrient uptake drops below ~16–18 °C. Humidity 60–80% for pollination.
// Capacitive soil sensor: irrigate below min, stop above max (hysteresis).

#define TOMATO_TEMP_MIN  18.0f
#define TOMATO_TEMP_MAX  30.0f
#define TOMATO_HUM_MIN   60.0f
#define TOMATO_HUM_MAX   80.0f
#define TOMATO_SOIL_MIN  40.0f
#define TOMATO_SOIL_MAX  70.0f

#endif
