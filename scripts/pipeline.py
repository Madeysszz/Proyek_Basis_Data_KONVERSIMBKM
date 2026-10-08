import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "database" / "norton_bisnis.db"
SCHEMA_PATH = BASE_DIR / "sql" / "schema.sql"
SOURCES = {
    "retail_transaction_log.csv": "retail",
    "cobrandgen_transaction_log.csv": "cobrand",
}
TRANSACTION_COLUMNS = [
    "business_key", "source_file", "channel_id", "campaign_id", "customer_id",
    "pricing_id", "device_id", "transaction_id", "detail_id", "callback_url",
    "status_activated", "psn", "redeem_code", "bill_number", "price",
    "is_revenue_valid", "subscription_start_date", "subscription_expired_at",
    "subscription_cancel_date", "duration_days", "is_churn", "puid", "pin",
    "email", "referral_code", "user_agent", "ip", "created_at", "updated_at",
    "deleted_at", "is_test", "ingested_at",
]


def read_source(filename):
    frame = pd.read_csv(DATA_DIR / filename, dtype="string", keep_default_na=False,
                        encoding="utf-8-sig")
    frame.columns = [column.strip() for column in frame.columns]
    return frame


def blank_to_none(value):
    if pd.isna(value):
        return None
    value = str(value).strip()
    return value or None


def parse_datetime(value):
    value = blank_to_none(value)
    if value is None:
        return None
    try:
        parsed = datetime.strptime(value.split(".", 1)[0], "%d/%m/%Y %H:%M:%S")
    except ValueError:
        return None
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def channel_from_bill(bill_number):
    bill_number = blank_to_none(bill_number)
    return bill_number.split("-", 1)[0].upper() if bill_number else None


def parse_device(raw_value):
    raw_value = blank_to_none(raw_value)
    if raw_value is None or raw_value.lower() == "null":
        return None, None, None, None
    try:
        parsed = json.loads(raw_value)
    except (json.JSONDecodeError, TypeError):
        return None, None, None, None
    device_id = hashlib.sha256(raw_value.encode("utf-8")).hexdigest()[:24]
    mobile = parsed.get("mobile")
    return device_id, blank_to_none(parsed.get("platform")), int(bool(mobile)), raw_value


def price_band(price):
    if price < 10000:
        return "pemula (<10rb)"
    if price <= 15000:
        return "menengah (10-15rb)"
    return "premium (>15rb)"


def extract():
    sources = {filename: read_source(filename) for filename in SOURCES}
    report = {
        filename: {
            "rows": len(frame),
            "columns": list(frame.columns),
            "blank_by_column": {
                column: int(frame[column].str.strip().eq("").sum())
                for column in frame.columns
                if frame[column].str.strip().eq("").any()
            },
        }
        for filename, frame in sources.items()
    }
    return sources, report


def transform(sources):
    rows = []
    device_rows = {}
    for filename, source_name in SOURCES.items():
        frame = sources[filename].copy()
        detail_column = f"{source_name}_transaction_log_detail_id" if source_name == "retail" else "cobrandgen_transaction_log_detail_id"
        if detail_column not in frame.columns:
            raise ValueError(f"Kolom detail transaksi tidak ditemukan: {detail_column}")
        required = {"transaction_id", "pricing_id", "customer_id", "status_activated", "bill_number", "price", "device_data"}
        absent = required.difference(frame.columns)
        if absent:
            raise ValueError(f"Kolom CSV {filename} tidak lengkap: {sorted(absent)}")

        frame["source_file"] = filename
        frame["channel_id"] = frame["bill_number"].map(channel_from_bill)
        frame["campaign_id"] = frame["camp_id"].map(blank_to_none) if "camp_id" in frame else None
        frame["customer_id"] = frame["customer_id"].map(blank_to_none)
        frame["pricing_id"] = frame["pricing_id"].map(blank_to_none)
        frame["detail_id"] = frame[detail_column].map(blank_to_none)
        for column in ["created_at", "updated_at", "deleted_at", "subscription_start_date",
                       "subscription_expired_at", "subscription_cancel_date"]:
            if column not in frame:
                frame[column] = ""
            frame[column] = frame[column].map(parse_datetime)

        frame["status_activated"] = frame["status_activated"].str.strip().str.upper()
        invalid_status = ~frame["status_activated"].isin(["ACTIVE", "CANCEL", "PENDING", "FAILED"])
        if invalid_status.any():
            raise ValueError(f"Status tidak didukung pada {filename}: {frame.loc[invalid_status, 'status_activated'].unique().tolist()}")

        frame["price"] = pd.to_numeric(frame["price"], errors="coerce")
        frame["is_revenue_valid"] = (frame["price"].fillna(0) > 0).astype("int64")
        frame["is_test"] = frame["bill_number"].str.startswith("TESTLOCAL").astype("int64")

        durations = []
        churn_flags = []
        device_ids = []
        for row in frame.itertuples(index=False):
            start = getattr(row, "subscription_start_date")
            expired = getattr(row, "subscription_expired_at")
            cancelled = getattr(row, "subscription_cancel_date")
            duration = None
            if start and expired:
                days = (datetime.fromisoformat(expired) - datetime.fromisoformat(start)).days
                duration = days if days > 0 else None
            durations.append(duration)
            churn_flags.append(int(row.status_activated == "CANCEL" and
                                   (not expired or not cancelled or cancelled < expired)))
            device_id, platform, mobile, raw_json = parse_device(getattr(row, "device_data"))
            device_ids.append(device_id)
            if device_id:
                device_rows[device_id] = (platform, mobile, raw_json)

        frame["duration_days"] = durations
        frame["is_churn"] = churn_flags
        frame["device_id"] = device_ids
        frame["business_key"] = (
            source_name + "|" + frame["transaction_id"].fillna("").astype(str) + "|" +
            frame["detail_id"].fillna("").astype(str) + "|" + frame["bill_number"].fillna("").astype(str)
        )
        duplicate_number = frame.groupby("business_key", sort=False).cumcount()
        frame.loc[duplicate_number.gt(0), "business_key"] += "|duplicate:" + duplicate_number[duplicate_number.gt(0)].astype(str)
        for column in ["callback_url", "psn", "redeem_code", "bill_number", "puid", "pin",
                       "email", "referral_code", "user_agent", "ip"]:
            if column not in frame:
                frame[column] = None
            frame[column] = frame[column].map(blank_to_none)
        frame["ingested_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        rows.append(frame)

    logs = pd.concat(rows, ignore_index=True)
    logs = logs.rename(columns={"camp_id": "campaign_id"}) if "campaign_id" not in logs else logs
    for column in TRANSACTION_COLUMNS:
        if column not in logs:
            logs[column] = None
    logs = logs[TRANSACTION_COLUMNS].copy()
    if logs["channel_id"].isna().any():
        raise ValueError(f"Transaksi tanpa kanal dari bill_number: {int(logs['channel_id'].isna().sum())}")
    logs["price"] = logs["price"].where(logs["price"].notna(), None)
    logs["duration_days"] = logs["duration_days"].where(logs["duration_days"].notna(), None)
    logs["is_revenue_valid"] = logs["is_revenue_valid"].astype("int64")
    logs["is_churn"] = logs["is_churn"].astype("int64")
    logs["is_test"] = logs["is_test"].astype("int64")

    channels = {}
    labels = {
        "TSEL": "Cobrand Telkomsel",
        "RETAIL": "Retail langsung",
        "DIGIFLAZZ": "Distributor Digiflazz",
        "TESTLOCAL": "TESTLOCAL",
    }
    for channel_id in sorted(logs["channel_id"].dropna().unique()):
        channels[channel_id] = (labels.get(channel_id, channel_id), None)

    campaign_ids = sorted(logs["campaign_id"].dropna().unique())
    campaigns = {campaign_id: (None, None) for campaign_id in campaign_ids}

    customers = {}
    for customer_id, group in logs.dropna(subset=["customer_id"]).groupby("customer_id", sort=True):
        observed_dates = group["created_at"].dropna()
        valid_prices = group.loc[group["is_revenue_valid"].eq(1), "price"]
        customers[customer_id] = (
            observed_dates.min() if not observed_dates.empty else None,
            observed_dates.max() if not observed_dates.empty else None,
            int(len(group)),
            int(valid_prices.sum()) if not valid_prices.empty else 0,
        )

    pricings = {}
    for pricing_id, group in logs.dropna(subset=["pricing_id", "price"]).groupby("pricing_id", sort=True):
        valid_prices = group.loc[group["is_revenue_valid"].eq(1), "price"]
        observed = (valid_prices if not valid_prices.empty else group["price"]).astype("int64")
        modal_price = int(observed.mode().iloc[0])
        pricings[pricing_id] = (modal_price, price_band(modal_price), group["created_at"].dropna().min())

    invalid_references = {
        "missing_channel": int(logs["channel_id"].isna().sum()),
        "missing_pricing_master": int((logs["pricing_id"].notna() & ~logs["pricing_id"].isin(pricings)).sum()),
        "missing_customer_master": int((logs["customer_id"].notna() & ~logs["customer_id"].isin(customers)).sum()),
        "missing_campaign_master": int((logs["campaign_id"].notna() & ~logs["campaign_id"].isin(campaigns)).sum()),
        "missing_device_master": int((logs["device_id"].notna() & ~logs["device_id"].isin(device_rows)).sum()),
    }
    if any(invalid_references.values()):
        raise ValueError(f"Terdapat foreign key yang tidak dapat dipetakan: {invalid_references}")
    return logs, channels, campaigns, customers, pricings, device_rows, invalid_references


def upsert(con, table, columns, rows, conflict_column, preserve=()):
    if not rows:
        return
    names = ", ".join(columns)
    marks = ", ".join("?" for _ in columns)
    updates = [column for column in columns if column != conflict_column and column not in preserve]
    assignments = ", ".join(f"{column}=excluded.{column}" for column in updates)
    sql = (f"INSERT INTO {table} ({names}) VALUES ({marks}) "
           f"ON CONFLICT({conflict_column}) DO UPDATE SET {assignments}")
    con.executemany(sql, rows)


def load(logs, channels, campaigns, customers, pricings, devices, db_path=DB_PATH):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    con.execute("BEGIN")
    try:
        upsert(con, "channel", ["channel_id", "channel_name", "description"],
               [(key, *value) for key, value in channels.items()], "channel_id")
        upsert(con, "campaign", ["campaign_id", "cobrand_partner", "campaign_name"],
               [(key, *value) for key, value in campaigns.items()], "campaign_id")
        upsert(con, "customer", ["customer_id", "first_seen_at", "last_seen_at", "n_transactions", "total_spend"],
               [(key, *value) for key, value in customers.items()], "customer_id")
        upsert(con, "pricing", ["pricing_id", "price", "price_band", "first_seen_at"],
               [(key, *value) for key, value in pricings.items()], "pricing_id")
        upsert(con, "device_profile", ["device_id", "platform", "is_mobile", "model", "raw_json"],
               [(key, value[0], value[1], json.loads(value[2]).get("model") or None, value[2])
                for key, value in devices.items()], "device_id")
        transaction_rows = []
        for row in logs.itertuples(index=False, name=None):
            values = []
            for value in row:
                if pd.isna(value):
                    values.append(None)
                elif hasattr(value, "item"):
                    values.append(value.item())
                else:
                    values.append(value)
            transaction_rows.append(tuple(values))
        upsert(con, "transaction_log", TRANSACTION_COLUMNS, transaction_rows,
               "business_key", preserve=("ingested_at",))
        con.commit()
    except Exception:
        con.rollback()
        raise
    return con


def validate(con, source_counts, transformed_count):
    table_names = ["channel", "campaign", "customer", "pricing", "device_profile", "transaction_log"]
    counts = {table: con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in table_names}
    foreign_key_errors = con.execute("PRAGMA foreign_key_check").fetchall()
    duplicate_keys = con.execute(
        "SELECT COUNT(*) FROM (SELECT business_key FROM transaction_log GROUP BY business_key HAVING COUNT(*) > 1)"
    ).fetchone()[0]
    missing_source_rows = transformed_count - counts["transaction_log"]
    if foreign_key_errors or duplicate_keys or missing_source_rows:
        raise RuntimeError({"foreign_key_errors": foreign_key_errors[:10],
                            "duplicate_business_keys": duplicate_keys,
                            "source_rows_not_loaded": missing_source_rows})
    return {
        "source_rows": source_counts,
        "source_total": sum(source_counts.values()),
        "transformed_rows": transformed_count,
        "database_counts": counts,
        "duplicate_business_keys": duplicate_keys,
        "foreign_key_errors": len(foreign_key_errors),
        "foreign_key_check": "lulus" if not foreign_key_errors else "gagal",
        "foreign_keys_enabled": con.execute("PRAGMA foreign_keys").fetchone()[0] == 1,
    }


def main():
    parser = argparse.ArgumentParser(description="ETL transaksi Norton ke SQLite")
    parser.add_argument("--database", type=Path, default=DB_PATH)
    args = parser.parse_args()
    sources, extract_report = extract()
    print("HASIL EXTRACT")
    for filename, report in extract_report.items():
        blank_cells = sum(report["blank_by_column"].values())
        print(f"{filename}: {report['rows']} baris, {len(report['columns'])} kolom, {blank_cells} sel kosong")
        print("Kolom kosong:", report["blank_by_column"])
        print("Kolom:", ", ".join(report["columns"]))

    logs, channels, campaigns, customers, pricings, devices, references = transform(sources)
    con = load(logs, channels, campaigns, customers, pricings, devices, args.database)
    source_counts = {filename: len(frame) for filename, frame in sources.items()}
    report = validate(con, source_counts, len(logs))
    report["reference_validation"] = references
    report["parsed_device_profiles"] = len(devices)
    report["missing_device_payloads"] = int(logs["device_id"].isna().sum())
    con.close()
    print("\nHASIL VALIDASI")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nDatabase operasional: {args.database}")


if __name__ == "__main__":
    main()
