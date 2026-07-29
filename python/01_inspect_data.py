from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_FOLDER = PROJECT_ROOT / "data" / "raw"

excel_files = list(RAW_FOLDER.glob("*.xlsx"))

if not excel_files:
    print("No Excel file found!")
    exit()

file = excel_files[0]

print(f"Reading: {file.name}")

workbook = pd.ExcelFile(file)

print("\nSheets:")
print(workbook.sheet_names)

for sheet in workbook.sheet_names:
    df = pd.read_excel(file, sheet_name=sheet)

    print("\n" + "=" * 60)
    print(f"Sheet: {sheet}")
    print(f"Rows: {len(df):,}")
    print(f"Columns: {len(df.columns)}")

    print("\nColumn Names:")
    print(df.columns.tolist())

    print("\nFirst Five Records:")
    print(df.head()