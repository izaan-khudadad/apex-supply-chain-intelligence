"""Load validated CSV rows and monthly carrier KPIs into MySQL."""

from __future__ import annotations

from sqlalchemy.engine import Engine


CREATE_TABLES = {
    "suppliers": """
        CREATE TABLE suppliers (
            supplier_id VARCHAR(16) PRIMARY KEY,
            supplier_name VARCHAR(120) NOT NULL,
            supplier_region VARCHAR(40) NOT NULL,
            lead_time_days INT NOT NULL,
            on_time_rate DECIMAL(5,3) NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "products": """
        CREATE TABLE products (
            product_id VARCHAR(16) PRIMARY KEY,
            product_name VARCHAR(100) NOT NULL,
            category VARCHAR(40) NOT NULL,
            unit_weight_kg DECIMAL(10,2) NOT NULL,
            unit_cost_usd DECIMAL(12,2) NOT NULL,
            supplier_id VARCHAR(16) NOT NULL,
            INDEX idx_products_supplier (supplier_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "warehouses": """
        CREATE TABLE warehouses (
            warehouse_id VARCHAR(16) PRIMARY KEY,
            warehouse_name VARCHAR(120) NOT NULL,
            city VARCHAR(80) NOT NULL,
            state VARCHAR(10) NOT NULL,
            latitude DECIMAL(10,6) NOT NULL,
            longitude DECIMAL(10,6) NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "carriers": """
        CREATE TABLE carriers (
            carrier_id VARCHAR(16) PRIMARY KEY,
            carrier_name VARCHAR(100) NOT NULL,
            service_type VARCHAR(30) NOT NULL,
            base_cost_usd DECIMAL(10,2) NOT NULL,
            cost_per_mile_usd DECIMAL(10,3) NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "routes": """
        CREATE TABLE routes (
            route_id VARCHAR(16) PRIMARY KEY,
            origin_warehouse_id VARCHAR(16) NOT NULL,
            destination_city VARCHAR(80) NOT NULL,
            destination_state VARCHAR(10) NOT NULL,
            distance_miles INT NOT NULL,
            route_zone VARCHAR(20) NOT NULL,
            INDEX idx_routes_warehouse (origin_warehouse_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "shipments": """
        CREATE TABLE shipments (
            shipment_id VARCHAR(20) PRIMARY KEY,
            order_date DATE NOT NULL,
            product_id VARCHAR(16) NOT NULL,
            supplier_id VARCHAR(16) NOT NULL,
            warehouse_id VARCHAR(16) NOT NULL,
            route_id VARCHAR(16) NOT NULL,
            carrier_id VARCHAR(16) NOT NULL,
            quantity INT NOT NULL,
            weight_kg DECIMAL(10,2) NOT NULL,
            shipping_cost_usd DECIMAL(12,2) NOT NULL,
            estimated_delivery_date DATE NOT NULL,
            actual_delivery_date DATE NULL,
            delivery_delay_days INT NULL,
            status VARCHAR(20) NOT NULL,
            INDEX idx_shipments_order_date (order_date),
            INDEX idx_shipments_status (status),
            INDEX idx_shipments_carrier (carrier_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
}

SUMMARY_DDL = """
    CREATE TABLE carrier_monthly_summary (
        month CHAR(7) NOT NULL,
        carrier_id VARCHAR(16) NOT NULL,
        shipment_count INT NOT NULL,
        completed_shipments INT NOT NULL,
        on_time_shipments INT NOT NULL,
        delayed_shipments INT NOT NULL,
        on_time_rate_pct DECIMAL(6,2) NULL,
        average_delivery_delay_days DECIMAL(7,2) NULL,
        total_shipping_cost_usd DECIMAL(14,2) NOT NULL,
        average_shipping_cost_usd DECIMAL(12,2) NOT NULL,
        PRIMARY KEY (month, carrier_id),
        INDEX idx_summary_carrier (carrier_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

INSERT_ORDER = ("suppliers", "products", "warehouses", "carriers", "routes", "shipments")
DROP_ORDER = ("carrier_monthly_summary", "shipments", "routes", "products", "warehouses", "carriers", "suppliers")
INTEGER_COLUMNS = {"lead_time_days", "distance_miles", "quantity", "delivery_delay_days"}
DECIMAL_COLUMNS = {
    "unit_weight_kg", "unit_cost_usd", "on_time_rate", "latitude", "longitude",
    "base_cost_usd", "cost_per_mile_usd", "weight_kg", "shipping_cost_usd",
}


def _convert_value(column: str, value: str) -> str | int | float | None:
    if value == "":
        return None
    if column in INTEGER_COLUMNS:
        return int(value)
    if column in DECIMAL_COLUMNS:
        return float(value)
    return value


def load_mysql(engine: Engine, data: dict[str, list[dict[str, str]]]) -> int:
    """Rebuild project tables from validated data and return summary row count."""
    with engine.begin() as connection:
        for table in DROP_ORDER:
            connection.exec_driver_sql(f"DROP TABLE IF EXISTS `{table}`")

        for table in INSERT_ORDER:
            connection.exec_driver_sql(CREATE_TABLES[table])
            columns = list(data[table][0])
            column_sql = ", ".join(f"`{column}`" for column in columns)
            placeholders = ", ".join("%s" for _ in columns)
            insert_sql = f"INSERT INTO `{table}` ({column_sql}) VALUES ({placeholders})"
            values = [
                tuple(_convert_value(column, row[column]) for column in columns)
                for row in data[table]
            ]
            connection.exec_driver_sql(insert_sql, values)

        connection.exec_driver_sql(SUMMARY_DDL)
        connection.exec_driver_sql("""
            INSERT INTO carrier_monthly_summary (
                month, carrier_id, shipment_count, completed_shipments,
                on_time_shipments, delayed_shipments, on_time_rate_pct,
                average_delivery_delay_days, total_shipping_cost_usd,
                average_shipping_cost_usd
            )
            SELECT
                CONCAT(YEAR(order_date), '-', LPAD(MONTH(order_date), 2, '0')) AS month,
                carrier_id,
                COUNT(*),
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
            GROUP BY CONCAT(YEAR(order_date), '-', LPAD(MONTH(order_date), 2, '0')), carrier_id
        """)
        summary_count = connection.exec_driver_sql(
            "SELECT COUNT(*) FROM carrier_monthly_summary"
        ).scalar_one()
    return int(summary_count)
