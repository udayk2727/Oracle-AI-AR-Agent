from __future__ import annotations

import os
from pathlib import Path

import oracledb
import pandas as pd
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_FOLDER = PROJECT_ROOT / "data" / "raw"

BATCH_SIZE = 5000


def get_connection() -> oracledb.Connection:
    load_dotenv(PROJECT_ROOT / ".env")

    required_variables = [
        "ORACLE_USER",
        "ORACLE_PASSWORD",
        "ORACLE_HOST",
        "ORACLE_PORT",
        "ORACLE_SERVICE",
    ]

    missing = [
        variable
        for variable in required_variables
        if not os.getenv(variable)
    ]

    if missing:
        raise RuntimeError(
            "Missing environment variables: " + ", ".join(missing)
        )

    return oracledb.connect(
        user=os.environ["ORACLE_USER"],
        password=os.environ["ORACLE_PASSWORD"],
        host=os.environ["ORACLE_HOST"],
        port=int(os.environ["ORACLE_PORT"]),
        service_name=os.environ["ORACLE_SERVICE"],
    )


def find_excel_file() -> Path:
    excel_files = list(RAW_FOLDER.glob("*.xlsx"))

    if not excel_files:
        raise FileNotFoundError(
            f"No Excel file found inside {RAW_FOLDER}"
        )

    return excel_files[0]


def read_source_data(excel_file: Path) -> pd.DataFrame:
    workbook = pd.ExcelFile(excel_file)
    frames: list[pd.DataFrame] = []

    for sheet_name in workbook.sheet_names:
        print(f"Reading sheet: {sheet_name}")

        frame = pd.read_excel(
            excel_file,
            sheet_name=sheet_name,
        )

        frame["SOURCE_SHEET"] = sheet_name
        frames.append(frame)

    data = pd.concat(frames, ignore_index=True)

    print(f"Rows read from Excel: {len(data):,}")
    return data


def prepare_records(
    data: pd.DataFrame,
    source_file: str,
) -> list[tuple]:
    data = data.rename(
        columns={
            "Invoice": "invoice_no",
            "StockCode": "stock_code",
            "Description": "description",
            "Quantity": "quantity",
            "InvoiceDate": "invoice_date",
            "Price": "unit_price",
            "Customer ID": "customer_id",
            "Country": "country",
        }
    )

    required_columns = [
        "invoice_no",
        "stock_code",
        "description",
        "quantity",
        "invoice_date",
        "unit_price",
        "customer_id",
        "country",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in data.columns
    ]

    if missing_columns:
        raise ValueError(
            "Missing source columns: " + ", ".join(missing_columns)
        )

    data["invoice_date"] = pd.to_datetime(
        data["invoice_date"],
        errors="coerce",
    )

    data["quantity"] = pd.to_numeric(
        data["quantity"],
        errors="coerce",
    )

    data["unit_price"] = pd.to_numeric(
        data["unit_price"],
        errors="coerce",
    )

    data["customer_id"] = pd.to_numeric(
        data["customer_id"],
        errors="coerce",
    )

    data = data.where(pd.notna(data), None)

    records: list[tuple] = []

    for row in data.itertuples(index=False):
        customer_id = (
            None
            if pd.isna(row.customer_id)
            else int(row.customer_id)
        )

        invoice_date = (
            None
            if pd.isna(row.invoice_date)
            else row.invoice_date.to_pydatetime()
        )

        records.append(
            (
                str(row.invoice_no)
                if row.invoice_no is not None
                else None,
                str(row.stock_code)
                if row.stock_code is not None
                else None,
                str(row.description)[:500]
                if row.description is not None
                else None,
                row.quantity,
                invoice_date,
                row.unit_price,
                customer_id,
                str(row.country)[:100]
                if row.country is not None
                else None,
                source_file,
            )
        )

    return records


def load_staging(
    connection: oracledb.Connection,
    records: list[tuple],
) -> None:
    insert_sql = """
        INSERT INTO stg_retail_transactions
        (
            invoice_no,
            stock_code,
            description,
            quantity,
            invoice_date,
            unit_price,
            customer_id,
            country,
            source_file
        )
        VALUES
        (
            :1, :2, :3, :4, :5,
            :6, :7, :8, :9
        )
    """

    cursor = connection.cursor()

    try:
        cursor.execute(
            "TRUNCATE TABLE stg_retail_transactions"
        )

        total = len(records)

        for start in range(0, total, BATCH_SIZE):
            batch = records[start : start + BATCH_SIZE]

            cursor.executemany(
                insert_sql,
                batch,
                batcherrors=True,
            )

            errors = cursor.getbatcherrors()

            if errors:
                for error in errors[:10]:
                    print(
                        "Rejected row offset:",
                        start + error.offset,
                        "| Error:",
                        error.message,
                    )

                raise RuntimeError(
                    f"{len(errors)} rows failed in the current batch."
                )

            connection.commit()

            loaded = min(start + BATCH_SIZE, total)
            print(f"Loaded {loaded:,} of {total:,} rows")

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()


def main() -> None:
    excel_file = find_excel_file()
    data = read_source_data(excel_file)

    records = prepare_records(
        data=data,
        source_file=excel_file.name,
    )

    print(f"Prepared records: {len(records):,}")

    connection = get_connection()

    try:
        load_staging(connection, records)
    finally:
        connection.close()

    print("Staging load completed successfully.")


if __name__ == "__main__":
    main()