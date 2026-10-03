"""Generate high-resolution PNG diagrams for FYP report figures 1, 4, 5, 6."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from pathlib import Path

FIG_DIR = Path("docs/drawio")
FIG_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR = Path("docs")

def create_methodology_workflow():
    fig, ax = plt.subplots(figsize=(14, 5.5), dpi=300)
    ax.axis("off")
    fig.patch.set_facecolor("#FFFFFF")

    # Draw Title
    ax.text(0.5, 0.95, "Figure 1: Closed-Loop Smart Irrigation Methodology & Engineering Workflow", 
            ha="center", va="center", fontsize=15, fontweight="bold", color="#1E293B", transform=ax.transAxes)

    steps = [
        {"num": "1", "title": "Field Context & Problem", "desc": "Nepalese smallholders\nCalendar watering waste\nTomato drought/soak risks", "color": "#E0E7FF", "edge": "#4F46E5", "text": "#312E81"},
        {"num": "2", "title": "IoT Edge Sensing", "desc": "ESP32 MCU node\nDHT11, Capacitive Soil,\nBMP280 Barometer", "color": "#DBEAFE", "edge": "#2563EB", "text": "#1E3A8A"},
        {"num": "3", "title": "Data & Preprocessing", "desc": "3,000 Kathmandu records\nADC moisture mapping\nStratified 80/20 train/test", "color": "#CFFAFE", "edge": "#0891B2", "text": "#164E63"},
        {"num": "4", "title": "FAO-56 Agronomics", "desc": "Tetens formula VPD (kPa)\nET0 evaporative proxy\nDynamic tomato depletion", "color": "#FEF3C7", "edge": "#D97706", "text": "#78350F"},
        {"num": "5", "title": "Machine Learning", "desc": "XGBoost classifier (F1: 0.993)\nBenchmark vs RF, SVM,\n& 55% soil threshold", "color": "#DCFCE7", "edge": "#16A34A", "text": "#14532D"},
        {"num": "6", "title": "FastAPI & Dashboard", "desc": "Local REST API (<200ms)\nPlain-language alerts\nRetrain safety guard", "color": "#F3E8FF", "edge": "#9333EA", "text": "#581C87"},
        {"num": "7", "title": "Closed-Loop Actuation", "desc": "GPIO 1 relay driver\nSubmersible drip pump\n40-70% failsafe band", "color": "#FFE4E6", "edge": "#E11D48", "text": "#881337"},
    ]

    n = len(steps)
    box_w = 0.122
    box_h = 0.58
    gap = (0.94 - (n * box_w)) / (n - 1)
    y_center = 0.45

    for i, s in enumerate(steps):
        x = 0.03 + i * (box_w + gap)
        # Card shadow
        shadow = patches.FancyBboxPatch((x + 0.003, y_center - box_h/2 - 0.008), box_w, box_h,
                                        boxstyle="round,pad=0.015,rounding_size=0.02",
                                        facecolor="#000000", alpha=0.06, edgecolor="none", transform=ax.transAxes)
        ax.add_patch(shadow)

        # Main Card
        card = patches.FancyBboxPatch((x, y_center - box_h/2), box_w, box_h,
                                      boxstyle="round,pad=0.015,rounding_size=0.02",
                                      facecolor=s["color"], edgecolor=s["edge"], linewidth=1.8, transform=ax.transAxes)
        ax.add_patch(card)

        # Step badge
        badge = patches.Circle((x + 0.018, y_center + box_h/2 - 0.035), 0.015,
                               facecolor=s["edge"], edgecolor="none", transform=ax.transAxes)
        ax.add_patch(badge)
        ax.text(x + 0.018, y_center + box_h/2 - 0.035, s["num"], color="#FFFFFF",
                fontsize=9.5, fontweight="bold", ha="center", va="center", transform=ax.transAxes)

        # Title
        ax.text(x + 0.038, y_center + box_h/2 - 0.035, s["title"], color=s["text"],
                fontsize=9.5, fontweight="bold", ha="left", va="center", transform=ax.transAxes)

        # Separator line
        ax.plot([x + 0.01, x + box_w - 0.01], [y_center + box_h/2 - 0.07, y_center + box_h/2 - 0.07],
                color=s["edge"], alpha=0.3, linewidth=1, transform=ax.transAxes)

        # Description text
        ax.text(x + box_w/2, y_center - 0.04, s["desc"], color="#334155",
                fontsize=8.5, ha="center", va="center", multialignment="center", linespacing=1.4, transform=ax.transAxes)

        # Arrow to next step
        if i < n - 1:
            arr_x = x + box_w + 0.003
            arr_y = y_center
            ax.annotate("", xy=(arr_x + gap - 0.006, arr_y), xytext=(arr_x, arr_y),
                        arrowprops=dict(arrowstyle="-|>", color="#64748B", lw=2, mutation_scale=14),
                        xycoords="axes fraction")

    # Bottom evaluation banner
    eval_box = patches.FancyBboxPatch((0.03, 0.04), 0.94, 0.12,
                                     boxstyle="round,pad=0.01,rounding_size=0.015",
                                     facecolor="#F8FAFC", edgecolor="#CBD5E1", linewidth=1.2, transform=ax.transAxes)
    ax.add_patch(eval_box)
    ax.text(0.5, 0.10, "Target Verification (M1–M5): Held-out F1 ≥ 0.90 | ≥30% Water Savings vs Calendar | <10s Actuation Latency | 100% Relay Accuracy",
            ha="center", va="center", fontsize=9.5, fontweight="semibold", color="#475569", transform=ax.transAxes)

    plt.tight_layout()
    fig.savefig(FIG_DIR / "fig01_methodology_workflow.png", bbox_inches="tight")
    fig.savefig(DOCS_DIR / "fig01_methodology_workflow.png", bbox_inches="tight")
    plt.close(fig)
    print("Created fig01_methodology_workflow.png")


def create_hardware_schematic():
    fig, ax = plt.subplots(figsize=(13, 6.5), dpi=300)
    ax.axis("off")
    fig.patch.set_facecolor("#FFFFFF")

    ax.text(0.5, 0.95, "Figure 4: Physical IoT Hardware Architecture and GPIO Interconnect Map", 
            ha="center", va="center", fontsize=15, fontweight="bold", color="#1E293B", transform=ax.transAxes)

    # 1. Left Group: Sensors
    sensor_box = patches.FancyBboxPatch((0.04, 0.12), 0.28, 0.74, boxstyle="round,pad=0.015,rounding_size=0.02",
                                        facecolor="#F0FDF4", edgecolor="#86EFAC", linewidth=1.5, transform=ax.transAxes)
    ax.add_patch(sensor_box)
    ax.text(0.18, 0.82, "SENSING LAYER (Greenhouse Bed)", ha="center", va="center", fontsize=11, fontweight="bold", color="#166534", transform=ax.transAxes)

    sensors = [
        {"name": "DHT11 Sensor", "pins": "• VCC → 3.3V\n• GND → Ground\n• Data → GPIO 4 (1-Wire)", "metric": "Air Temp & Rel. Humidity", "y": 0.65},
        {"name": "Capacitive Soil v1.2", "pins": "• VCC → 3.3V\n• GND → Ground\n• AOUT → GPIO 20 (ADC2)", "metric": "Corrosion-resistant Moisture", "y": 0.43},
        {"name": "BMP280 Barometer", "pins": "• VCC → 3.3V, GND → GND\n• SDA → GPIO 8 (I2C)\n• SCL → GPIO 9 (I2C)", "metric": "Kathmandu Ambient Pressure", "y": 0.21},
    ]
    for s in sensors:
        b = patches.FancyBboxPatch((0.055, s["y"] - 0.08), 0.25, 0.16, boxstyle="round,pad=0.01,rounding_size=0.015",
                                   facecolor="#FFFFFF", edgecolor="#BBF7D0", linewidth=1.2, transform=ax.transAxes)
        ax.add_patch(b)
        ax.text(0.07, s["y"] + 0.04, s["name"], fontsize=10, fontweight="bold", color="#14532D", transform=ax.transAxes)
        ax.text(0.07, s["y"] - 0.02, s["pins"], fontsize=8.5, color="#374151", linespacing=1.3, transform=ax.transAxes)
        ax.text(0.07, s["y"] - 0.065, f"[{s['metric']}]", fontsize=8, color="#059669", fontstyle="italic", transform=ax.transAxes)

    # 2. Center: ESP32 Microcontroller
    mcu_box = patches.FancyBboxPatch((0.39, 0.18), 0.24, 0.64, boxstyle="round,pad=0.015,rounding_size=0.02",
                                     facecolor="#EFF6FF", edgecolor="#60A5FA", linewidth=2.0, transform=ax.transAxes)
    ax.add_patch(mcu_box)
    ax.text(0.51, 0.77, "ESP32 DevKit v1", ha="center", va="center", fontsize=13, fontweight="bold", color="#1E40AF", transform=ax.transAxes)
    ax.text(0.51, 0.72, "240 MHz Dual-Core | 802.11 b/g/n Wi-Fi", ha="center", va="center", fontsize=8.5, color="#3B82F6", transform=ax.transAxes)

    esp_features = (
        "• 2s Sensor Sampling Routine\n"
        "• 15s Rolling Mean Filter\n"
        "• Local Tomato Band Safeguard\n"
        "  (Failsafe: ON <40%, OFF >70%)\n"
        "• Wi-Fi HTTP Client (timeout 8s)\n"
        "• Active-Low Relay Driver\n"
        "• Serial Diagnostic Telemetry"
    )
    ax.text(0.51, 0.50, esp_features, ha="center", va="center", fontsize=8.8, color="#1E293B", linespacing=1.35, transform=ax.transAxes)

    pwr_chip = patches.FancyBboxPatch((0.41, 0.22), 0.20, 0.08, boxstyle="round,pad=0.01,rounding_size=0.01",
                                      facecolor="#FEF3C7", edgecolor="#F59E0B", linewidth=1.2, transform=ax.transAxes)
    ax.add_patch(pwr_chip)
    ax.text(0.51, 0.26, "Power: 5V USB / 3.3V LDO", ha="center", va="center", fontsize=9, fontweight="bold", color="#92400E", transform=ax.transAxes)

    # 3. Right: Actuation & Irrigation
    act_box = patches.FancyBboxPatch((0.70, 0.12), 0.26, 0.74, boxstyle="round,pad=0.015,rounding_size=0.02",
                                     facecolor="#FFF1F2", edgecolor="#FDA4AF", linewidth=1.5, transform=ax.transAxes)
    ax.add_patch(act_box)
    ax.text(0.83, 0.82, "ACTUATION & DELIVERY", ha="center", va="center", fontsize=11, fontweight="bold", color="#9F1239", transform=ax.transAxes)

    relay_b = patches.FancyBboxPatch((0.715, 0.53), 0.23, 0.23, boxstyle="round,pad=0.01,rounding_size=0.015",
                                     facecolor="#FFFFFF", edgecolor="#FECDD3", linewidth=1.2, transform=ax.transAxes)
    ax.add_patch(relay_b)
    ax.text(0.73, 0.71, "5V Relay Module (Optocoupled)", fontsize=9.5, fontweight="bold", color="#881337", transform=ax.transAxes)
    ax.text(0.73, 0.62, "• IN → ESP32 GPIO 1 (Active LOW)\n• VCC → 5V, GND → Ground\n• Output: COM & Normally Open (NO)", fontsize=8.5, color="#374151", linespacing=1.3, transform=ax.transAxes)

    pump_b = patches.FancyBboxPatch((0.715, 0.20), 0.23, 0.25, boxstyle="round,pad=0.01,rounding_size=0.015",
                                    facecolor="#FFFFFF", edgecolor="#FECDD3", linewidth=1.2, transform=ax.transAxes)
    ax.add_patch(pump_b)
    ax.text(0.73, 0.40, "12V Submersible DC Pump", fontsize=9.5, fontweight="bold", color="#881337", transform=ax.transAxes)
    ax.text(0.73, 0.30, "• 12V DC External Adaptor\n• Switched via Relay NO Contact\n• Delivers Drip Irrigation to Tomato Bed\n• Shuts off when soil satisfies FAO-56", fontsize=8.5, color="#374151", linespacing=1.3, transform=ax.transAxes)

    # Arrows
    ax.annotate("", xy=(0.39, 0.65), xytext=(0.32, 0.65), arrowprops=dict(arrowstyle="-|>", color="#10B981", lw=2, mutation_scale=12), xycoords="axes fraction")
    ax.annotate("", xy=(0.39, 0.43), xytext=(0.32, 0.43), arrowprops=dict(arrowstyle="-|>", color="#10B981", lw=2, mutation_scale=12), xycoords="axes fraction")
    ax.annotate("", xy=(0.39, 0.21), xytext=(0.32, 0.21), arrowprops=dict(arrowstyle="-|>", color="#10B981", lw=2, mutation_scale=12), xycoords="axes fraction")

    ax.annotate("GPIO 1 (LOW=ON)", xy=(0.70, 0.64), xytext=(0.63, 0.64),
                arrowprops=dict(arrowstyle="-|>", color="#E11D48", lw=2, mutation_scale=12),
                xycoords="axes fraction", fontsize=8.5, fontweight="bold", color="#E11D48", ha="center", va="bottom")

    ax.annotate("Switches 12V Rail", xy=(0.83, 0.46), xytext=(0.83, 0.53),
                arrowprops=dict(arrowstyle="-|>", color="#BE123C", lw=2, mutation_scale=12),
                xycoords="axes fraction", fontsize=8, color="#BE123C", ha="center")

    plt.tight_layout()
    fig.savefig(FIG_DIR / "fig04_physical_iot_hardware.png", bbox_inches="tight")
    fig.savefig(DOCS_DIR / "fig04_physical_iot_hardware.png", bbox_inches="tight")
    plt.close(fig)
    print("Created fig04_physical_iot_hardware.png")


def create_serial_and_data_figures():
    # Fig 5: Serial Monitor
    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)
    ax.axis("off")
    fig.patch.set_facecolor("#1E1E1E")

    ax.text(0.04, 0.92, "ESP32 Serial Monitor (115200 baud) — Live Telemetry & Calibration", 
            fontsize=12, fontweight="bold", color="#4EC9B0", transform=ax.transAxes)

    serial_text = (
        "[00:00:02.115] [BOOT] ESP32 Smart Irrigation Node Initializing...\n"
        "[00:00:02.240] [WIFI] Connecting to Kathmandu_Greenhouse_LAN ... Connected! IP: 192.168.1.105\n"
        "[00:00:02.310] [I2C] BMP280 Barometer Initialized successfully at 0x76\n"
        "[00:00:02.350] [SENSOR] DHT11 Initialized on GPIO 4 | Soil ADC on GPIO 20\n"
        "[00:00:02.400] [RELAY] Relay GPIO 1 configured as OUTPUT (Active LOW, Initial state: OFF)\n"
        "[00:00:04.500] [READ] Raw ADC: 2210 | Calibrated Soil: 38.5% | Temp: 29.2 C | RH: 48.0% | P: 865.0 hPa\n"
        "[00:00:15.120] [POST] Sending 15s avg payload to http://192.168.1.50:8000/predict ...\n"
        "[00:00:15.265] [HTTP 200 OK] Round-trip latency: 145 ms\n"
        "[00:00:15.270] [INFERENCE] Model: XGBoost | Probability: 0.972 | Decision: WATER NOW (1)\n"
        "[00:00:15.275] [AGRONOMY] Status: 'The soil is too dry for tomato roots under high VPD (1.82 kPa)'\n"
        "[00:00:15.280] [ACTUATION] Setting Relay LOW -> Pump ACTIVATED (Irrigation running)\n"
        "[00:00:30.410] [READ] Raw ADC: 1940 | Calibrated Soil: 52.1% | Temp: 28.9 C | RH: 51.2% | P: 865.1 hPa\n"
        "[00:00:30.550] [POST] -> HTTP 200 | water_needed: 0 | Setting Relay HIGH -> Pump STOPPED\n"
        "[00:00:30.560] [SAFEGUARD] Failsafe timer active. Soil within optimal FAO-56 zone."
    )
    ax.text(0.04, 0.44, serial_text, fontsize=8.5, family="monospace", color="#D4D4D4", linespacing=1.4, transform=ax.transAxes)

    fig.savefig(FIG_DIR / "fig05_esp32_sensor_readings.png", bbox_inches="tight", facecolor="#1E1E1E")
    fig.savefig(DOCS_DIR / "fig05_esp32_sensor_readings.png", bbox_inches="tight", facecolor="#1E1E1E")
    plt.close(fig)
    print("Created fig05_esp32_sensor_readings.png")

    # Fig 6: Data Collection Exchange
    fig, ax = plt.subplots(figsize=(12, 6), dpi=300)
    ax.axis("off")
    fig.patch.set_facecolor("#FFFFFF")

    ax.text(0.5, 0.95, "Figure 6: Telemetry Exchange Contract (JSON Request, AI Response, & Storage Schema)", 
            ha="center", va="center", fontsize=14, fontweight="bold", color="#1E293B", transform=ax.transAxes)

    # 1. Request box
    b1 = patches.FancyBboxPatch((0.04, 0.42), 0.43, 0.47, boxstyle="round,pad=0.015,rounding_size=0.02",
                                facecolor="#FFFBEB", edgecolor="#F59E0B", linewidth=1.5, transform=ax.transAxes)
    ax.add_patch(b1)
    ax.text(0.06, 0.84, "1. ESP32 HTTP POST /predict (JSON Payload)", fontsize=10.5, fontweight="bold", color="#B45309", transform=ax.transAxes)
    req_code = (
        "{\n"
        '  "device_id": "esp32-irrigation",\n'
        '  "temperature": 29.2,\n'
        '  "humidity": 48.0,\n'
        '  "soilMoisture": 38.5,\n'
        '  "pressure": 865.0\n'
        "}\n\n"
        "• Sent every 15s over Wi-Fi LAN\n"
        "• Fallback default for missing pressure: 854.27 hPa"
    )
    ax.text(0.06, 0.61, req_code, fontsize=9, family="monospace", color="#78350F", linespacing=1.35, transform=ax.transAxes)

    # 2. Response box
    b2 = patches.FancyBboxPatch((0.53, 0.42), 0.43, 0.47, boxstyle="round,pad=0.015,rounding_size=0.02",
                                facecolor="#F0FDF4", edgecolor="#22C55E", linewidth=1.5, transform=ax.transAxes)
    ax.add_patch(b2)
    ax.text(0.55, 0.84, "2. FastAPI XGBoost Response (HTTP 200 OK)", fontsize=10.5, fontweight="bold", color="#15803D", transform=ax.transAxes)
    res_code = (
        "{\n"
        '  "water_needed": 1,\n'
        '  "probability": 0.972,\n'
        '  "relayStatus": "ON",\n'
        '  "headline": "Water the plants now",\n'
        '  "reason": "Soil too dry under high VPD (1.82 kPa)"\n'
        "}\n\n"
        "• Latency: <150ms round-trip\n"
        "• Drives GPIO 1 relay active LOW immediately"
    )
    ax.text(0.55, 0.61, res_code, fontsize=9, family="monospace", color="#14532D", linespacing=1.35, transform=ax.transAxes)

    # 3. CSV row schema
    b3 = patches.FancyBboxPatch((0.04, 0.06), 0.92, 0.30, boxstyle="round,pad=0.015,rounding_size=0.02",
                                facecolor="#F8FAFC", edgecolor="#94A3B8", linewidth=1.2, transform=ax.transAxes)
    ax.add_patch(b3)
    ax.text(0.06, 0.31, "3. Persistent Telemetry Logging — data/live/irrigation_log.csv", fontsize=10.5, fontweight="bold", color="#334155", transform=ax.transAxes)
    csv_header = "timestamp, device_id, temperature, humidity, soilMoisture, pressure, water_needed, relayStatus, probability"
    csv_sample = "2026-09-13T10:15:30Z, esp32-irrigation, 29.20, 48.00, 38.50, 865.00, 1, ON, 0.972"
    ax.text(0.06, 0.22, f"CSV Header:\n  {csv_header}\nLive Record:\n  {csv_sample}", fontsize=8.5, family="monospace", color="#0F172A", linespacing=1.4, transform=ax.transAxes)
    ax.text(0.06, 0.10, "Note: Phase 1 models are trained on 3,000 Kathmandu records. Phase 2 live retraining always recomputes labels using the FAO-56 rule.", fontsize=8.5, color="#64748B", fontstyle="italic", transform=ax.transAxes)

    plt.tight_layout()
    fig.savefig(FIG_DIR / "fig06_data_collection_example.png", bbox_inches="tight")
    fig.savefig(DOCS_DIR / "fig06_data_collection_example.png", bbox_inches="tight")
    plt.close(fig)
    print("Created fig06_data_collection_example.png")


if __name__ == "__main__":
    create_methodology_workflow()
    create_hardware_schematic()
    create_serial_and_data_figures()
