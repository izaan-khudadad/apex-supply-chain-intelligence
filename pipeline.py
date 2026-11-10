"""Run the local Apex data pipeline: generate, validate, and load into SQLite."""

from __future__ import annotations

import csv
import sqlite3
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from db_config import create_mysql_engine, has_mysql_secrets
from mysql_writer import load_mysql


PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data" / "simulated"
DATABASE_PATH = PROJECT_DIR / "data" / "apex_supply_chain.db"

# Each entry maps a CSV column to its SQLite type. Dates are stored as ISO text,
# which SQLite can sort and compare chronologically.
TABLE_COLUMNS = {
    "products": {
        "product_id": "TEXT PRIMARY KEY", "product_name": "TEXT NOT NULL",
        "category": "TEXT NOT NULL", "unit_weight_kg": "REAL NOT NULL",
        "unit_cost_usd": "REAL NOT NULL", "supplier_id": "TEXT NOT NULL",
    },
    "suppliers": {
        "supplier_id": "TEXT PRIMARY KEY", "supplier_name": "TEXT NOT NULL",
        "supplier_region": "TEXT NOT NULL", "lead_time_days": "INTEGER NOT NULL",
        "on_time_rate": "REAL NOT NULL",
    },
    "warehouses": {
        "warehouse_id": "TEXT PRIMARY KEY", "warehouse_name": "TEXT NOT NULL",
        "city": "TEXT NOT NULL", "state": "TEXT NOT NULL",
        "latitude": "REAL NOT NULL", "longitude": "REAL NOT NULL",
    },
    "carriers": {
        "carrier_id": "TEXT PRIMARY KEY", "carrier_name": "TEXT NOT NULL",
        "service_type": "TEXT NOT NULL", "base_cost_usd": "REAL NOT NULL",
        "cost_per_mile_usd": "REAL NOT NULL",
    },
    "routes": {
        "route_id": "TEXT PRIMARY KEY", "origin_warehouse_id": "TEXT NOT NULL",
        "destination_city": "TEXT NOT NULL", "destination_state": "TEXT NOT NULL",
        "distance_miles": "INTEGER NOT NULL", "route_zone": "TEXT NOT NULL",
    },
    "shipments": {
        "shipment_id": "TEXT PRIMARY KEY", "order_date": "TEXT NOT NULL",
        "product_id": "TEXT NOT NULL", "supplier_id": "TEXT NOT NULL",
        "warehouse_id": "TEXT NOT NULL", "route_id": "TEXT NOT NULL",
        "carrier_id": "TEXT NOT NULL", "quantity": "INTEGER NOT NULL",
        "weight_kg": "REAL NOT NULL", "shipping_cost_usd": "REAL NOT NULL",
        "estimated_delivery_date": "TEXT NOT NULL", "actual_delivery_date": "TEXT",
        "delivery_delay_days": "INTEGER", "status": "TEXT NOT NULL",
    },
}

INTEGER_COLUMNS = {
    "lead_time_days", "distance_miles", "quantity", "delivery_delay_days",
}
REAL_COLUMNS = {
    "unit_weight_kg", "unit_cost_usd", "on_time_rate", "latitude", "longitude",
    "base_cost_usd", "cost_per_mile_usd", "weight_kg", "shipping_cost_usd",
}


def read_csv(table: str) -> list[dict[str, str]]:
    path = DATA_DIR / f"{table}.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path}. Run the generator before loading data.")
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        expected = list(TABLE_COLUMNS[table])
        if reader.fieldnames != expected:
            raise ValueError(f"Unexpected columns in {path.name}: {reader.fieldnames}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"{path.name} contains no data rows.")
    return rows


def validate_data(data: dict[str, list[dict[str, str]]]) -> None:
    """Check IDs, references, dates, statuses, and basic numeric values."""
    for table, rows in data.items():
        id_column = f"{table[:-1] if table != 'shipments' else 'shipment'}_id"
        ids = [row[id_column] for row in rows]
        if len(ids) != len(set(ids)):
            raise ValueError(f"Duplicate {id_column} values found in {table}.csv")

    suppliers = {row["supplier_id"] for row in data["suppliers"]}
    products = {row["product_id"]: row for row in data["products"]}
    warehouses = {row["warehouse_id"] for row in data["warehouses"]}
    carriers = {row["carrier_id"] for row in data["carriers"]}
    routes = {row["route_id"]: row for row in data["routes"]}
    for product in data["products"]:
        if product["supplier_id"] not in suppliers:
            raise ValueError(f"Unknown supplier for product {product['product_id']}.")

    valid_statuses = {"Delivered", "Delayed", "In Transit", "Cancelled"}
    for shipment in data["shipments"]:
        shipment_id = shipment["shipment_id"]
        product = products.get(shipment["product_id"])
        route = routes.get(shipment["route_id"])
        if product is None or shipment["supplier_id"] not in suppliers:
            raise ValueError(f"Shipment {shipment_id} references an unknown product or supplier.")
        if shipment["supplier_id"] != product["supplier_id"]:
            raise ValueError(f"Shipment {shipment_id} supplier does not match its product.")
        if shipment["warehouse_id"] not in warehouses or shipment["carrier_id"] not in carriers or route is None:
            raise ValueError(f"Shipment {shipment_id} references an unknown warehouse, route, or carrier.")
        if route["origin_warehouse_id"] != shipment["warehouse_id"]:
            raise ValueError(f"Shipment {shipment_id} route starts at a different warehouse.")
        if shipment["status"] not in valid_statuses:
            raise ValueError(f"Shipment {shipment_id} has an unknown status.")
        if float(shipment["shipping_cost_usd"]) <= 0 or int(shipment["quantity"]) <= 0:
            raise ValueError(f"Shipment {shipment_id} has an invalid cost or quantity.")
        date.fromisoformat(shipment["order_date"])
        estimated = date.fromisoformat(shipment["estimated_delivery_date"])
        actual_text = shipment["actual_delivery_date"]
        if shipment["status"] in {"Delivered", "Delayed"}:
            if not actual_text:
                raise ValueError(f"Completed shipment {shipment_id} has no actual delivery date.")
            actual = date.fromisoformat(actual_text)
            should_be_delayed = actual > estimated
            if (shipment["status"] == "Delayed") != should_be_delayed:
                raise ValueError(f"Shipment {shipment_id} status conflicts with its delivery dates.")
        elif actual_text:
            raise ValueError(f"Open or cancelled shipment {shipment_id} unexpectedly has an actual date.")


def to_sql_value(column: str, value: str) -> str | int | float | None:
    if value == "":
        return None
    if column in INTEGER_COLUMNS:
        return int(value)
    if column in REAL_COLUMNS:
        return float(value)
    return value


def load_sqlite(data: dict[str, list[dict[str, str]]]) -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN")
        for table, columns in TABLE_COLUMNS.items():
            definitions = ", ".join(f'"{name}" {kind}' for name, kind in columns.items())
            connection.execute(f'DROP TABLE IF EXISTS "{table}"')
            connection.execute(f'CREATE TABLE "{table}" ({definitions})')
            column_names = list(columns)
            columns_sql = ", ".join(f'"{name}"' for name in column_names)
            placeholders = ", ".join("?" for _ in column_names)
            insert_sql = f'INSERT INTO "{table}" ({columns_sql}) VALUES ({placeholders})'
            values = [
                tuple(to_sql_value(column, row[column]) for column in column_names)
                for row in data[table]
            ]
            connection.executemany(insert_sql, values)

        connection.execute("CREATE INDEX idx_shipments_order_date ON shipments(order_date)")
        connection.execute("CREATE INDEX idx_shipments_status ON shipments(status)")
        connection.execute("CREATE INDEX idx_shipments_carrier ON shipments(carrier_id)")

        # Precompute monthly carrier KPIs so the dashboard can read a compact,
        # analysis-ready table instead of recalculating these metrics each time.
        connection.execute("DROP TABLE IF EXISTS carrier_monthly_summary")
        connection.execute("""
            CREATE TABLE carrier_monthly_summary (
                month TEXT NOT NULL,
                carrier_id TEXT NOT NULL,
                shipment_count INTEGER NOT NULL,
                completed_shipments INTEGER NOT NULL,
                on_time_shipments INTEGER NOT NULL,
                delayed_shipments INTEGER NOT NULL,
                on_time_rate_pct REAL,
                average_delivery_delay_days REAL,
                total_shipping_cost_usd REAL NOT NULL,
                average_shipping_cost_usd REAL NOT NULL,
                PRIMARY KEY (month, carrier_id)
            )
        """)
        connection.execute("""
            INSERT INTO carrier_monthly_summary (
                month, carrier_id, shipment_count, completed_shipments,
                on_time_shipments, delayed_shipments, on_time_rate_pct,
                average_delivery_delay_days, total_shipping_cost_usd,
                average_shipping_cost_usd
            )
            SELECT
                substr(order_date, 1, 7) AS month,
                carrier_id,
                COUNT(*) AS shipment_count,
                SUM(CASE WHEN status IN ('Delivered', 'Delayed') THEN 1 ELSE 0 END),
                SUM(CASE WHEN status = 'Delivered' THEN 1 ELSE 0 END),
                SUM(CASE WHEN status = 'Delayed' THEN 1 ELSE 0 END),
                ROUND(
                    100.0 * SUM(CASE WHEN status = 'Delivered' THEN 1 ELSE 0 END)
                    / NULLIF(SUM(CASE WHEN status IN ('Delivered', 'Delayed') THEN 1 ELSE 0 END), 0),
                    2
                ),
                ROUND(AVG(CASE WHEN status IN ('Delivered', 'Delayed')
                               THEN delivery_delay_days END), 2),
                ROUND(SUM(shipping_cost_usd), 2),
                ROUND(AVG(shipping_cost_usd), 2)
            FROM shipments
            GROUP BY substr(order_date, 1, 7), carrier_id
        """)
        connection.execute("CREATE INDEX idx_carrier_summary_month ON carrier_monthly_summary(month)")


def main() -> None:
    generator = PROJECT_DIR / "data_generator.py"
    if not generator.is_file():
        raise FileNotFoundError(f"Could not find {generator}")

    print("Step 1/3: Generating source CSV files...")
    subprocess.run([sys.executable, str(generator)], cwd=PROJECT_DIR, check=True)

    print("Step 2/3: Checking CSV data and relationships...")
    data = {table: read_csv(table) for table in TABLE_COLUMNS}
    validate_data(data)

    print("Step 3/3: Loading tables into SQLite...")
    load_sqlite(data)

    counts = Counter({table: len(rows) for table, rows in data.items()})
    print("\nPipeline completed successfully.")
    print(f"SQLite database: {DATABASE_PATH}")
    for table, row_count in counts.items():
        print(f"  {table}: {row_count:,} rows")
    with sqlite3.connect(DATABASE_PATH) as connection:
        summary_count = connection.execute("SELECT COUNT(*) FROM carrier_monthly_summary").fetchone()[0]
    print(f"  carrier_monthly_summary: {summary_count:,} rows")

    if has_mysql_secrets():
        print("Loading validated tables into MySQL...")
        engine = create_mysql_engine()
        try:
            mysql_summary_count = load_mysql(engine, data)
        finally:
            engine.dispose()
        print(f"  MySQL database loaded: carrier_monthly_summary has {mysql_summary_count:,} rows")
    else:
        print("MySQL load skipped: set up .streamlit/secrets.toml to enable it.")


if __name__ == "__main__":
    main()
