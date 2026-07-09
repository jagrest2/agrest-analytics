import pandas as pd
import os

print("--> PYTHON HAS SUCCESSFULLY STARTED THE SCRIPT <--")

csv_path = "app/data/2026/output3.csv"

if not os.path.exists(csv_path):
    print(f"CRITICAL ERROR: Can't find your file at: {os.path.abspath(csv_path)}")
    print("Are you running this script from your project root folder?")
else:
    print(f"Found the file! Reading master data from {csv_path}...")
    df = pd.read_csv(csv_path)

    for col in df.columns:
        converted = pd.to_numeric(df[col], errors='coerce')
        if not converted.isna().all():
            df[col] = converted

    print("Enforcing two decimal places across all analytics metrics...")
    df.to_csv(csv_path, index=False, float_format='%.2f')
    
    print("🎉 SUCCESS: Pristine 2-decimal data saved back to disk!")