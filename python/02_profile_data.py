from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_FOLDER = PROJECT_ROOT / "data" / "raw"
OUTPUT_FOLDER = PROJECT_ROOT / "data" / "processed"


def main() -> None:
    excel_files = list(RAW_FOLDER.glob("*.xlsx"))

    if not excel_files:
        raise FileNotFoundError(
            "No Excel file found inside data/raw."
        )

    raw_file = excel_files[0]
    workbook = pd.ExcelFile(raw_file)

    frames: list[pd.DataFrame] = []

    for sheet_name in workbook.sheet_names:
        df = pd.read_excel(raw_file, sheet_name=sheet_name)
        df["SourceSheet"] = sheet_name
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)

    print(f"Total rows: {len(combined):,}")
    print(f"Unique invoices: {combined['Invoice'].nunique():,}")
    print(f"Unique products: {combined['StockCode'].nunique():,}")
    print(f"Unique customers: {combined['Customer ID'].nunique():,}")
    print(f"Countries: {combined['Country'].nunique():,}")

    cancelled = combined[
        combined["Invoice"].astype(str).str.startswith("C")
    ]

    returns = combined[combined["Quantity"] < 0]
    missing_customers = combined["Customer ID"].isna().sum()

    print(f"Cancelled rows: {len(cancelled):,}")
    print(f"Negative quantity rows: {len(returns):,}")
    print(f"Rows with missing customer ID: {missing_customers:,}")

    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

    summary_file = OUTPUT_FOLDER / "data_profile_summary.txt"

    with summary_file.open("w", encoding="utf-8") as file:
        file.write(f"Total rows: {len(combined):,}\n")
        file.write(
            f"Unique invoices: "
            f"{combined['Invoice'].nunique():,}\n"
        )
        file.write(
            f"Unique products: "
            f"{combined['StockCode'].nunique():,}\n"
        )
        file.write(
            f"Unique customers: "
            f"{combined['Customer ID'].nunique():,}\n"
        )
        file.write(
            f"Countries: "
            f"{combined['Country'].nunique():,}\n"
        )
        file.write(f"Cancelled rows: {len(cancelled):,}\n")
        file.write(
            f"Negative quantity rows: {len(returns):,}\n"
        )
        file.write(
            f"Missing customer IDs: {missing_customers:,}\n"
        )

    print(f"\nProfile saved to: {summary_file}")


if __name__ == "__main__":
    main()