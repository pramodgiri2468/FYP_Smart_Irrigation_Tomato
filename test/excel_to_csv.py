import pandas as pd

# Input Excel file
input_file = "data/raw/Soil_Moisture_Temp_Humidity_Pressure_MotorOnOff.xlsx"

# Output CSV file
output_file = "data/irrigation_data.csv"

# Read Excel file
df = pd.read_excel(input_file)

# Convert to CSV
df.to_csv(output_file, index=False)

print("Excel file converted successfully!")
print(f"CSV file: {output_file}")