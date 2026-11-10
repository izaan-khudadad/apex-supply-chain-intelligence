"""Generate a reproducible, fictional supply-chain dataset for Apex Electronics.

Run from the project folder with:
    python data_generator.py

The script uses only Python's standard library. It writes CSV files to
data/simulated/ and can be rerun safely to replace those generated files.
"""

from __future__ import annotations

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "data" / "simulated"
DEFAULT_START_DATE = date(2025, 1, 1)
DEFAULT_SEED = 42

CATEGORIES = {
    "Computing": ["Laptop", "Desktop PC", "Monitor", "Keyboard", "Mouse", "Docking Station"],
    "Audio": ["Headphones", "Bluetooth Speaker", "Microphone", "Webcam"],
    "Mobile": ["Smartphone", "Tablet", "Charger", "Power Bank", "Protective Case"],
    "Networking": ["Wi-Fi Router", "Network Switch", "Access Point", "Ethernet Adapter"],
    "Components": ["SSD", "Memory Kit", "Graphics Card", "Processor", "Power Supply"],
}

WAREHOUSE_SITES = [
    ("Seattle", "WA", 47.6062, -122.3321),
    ("Portland", "OR", 45.5152, -122.6784),
    ("San Francisco", "CA", 37.7749, -122.4194),
    ("Los Angeles", "CA", 34.0522, -118.2437),
    ("San Diego", "CA", 32.7157, -117.1611),
    ("Phoenix", "AZ", 33.4484, -112.0740),
    ("Denver", "CO", 39.7392, -104.9903),
    ("Dallas", "TX", 32.7767, -96.7970),
    ("Houston", "TX", 29.7604, -95.3698),
    ("Minneapolis", "MN", 44.9778, -93.2650),
    ("Chicago", "IL", 41.8781, -87.6298),
    ("St. Louis", "MO", 38.6270, -90.1994),
    ("Nashville", "TN", 36.1627, -86.7816),
    ("Atlanta", "GA", 33.7490, -84.3880),
    ("Miami", "FL", 25.7617, -80.1918),
    ("Charlotte", "NC", 35.2271, -80.8431),
    ("Washington", "DC", 38.9072, -77.0369),
    ("Philadelphia", "PA", 39.9526, -75.1652),
    ("New York", "NY", 40.7128, -74.0060),
    ("Boston", "MA", 42.3601, -71.0589),
]

DESTINATIONS = [
    ("Las Vegas", "NV", 36.1699, -115.1398),
    ("Sacramento", "CA", 38.5816, -121.4944),
    ("Boise", "ID", 43.6150, -116.2023),
    ("Salt Lake City", "UT", 40.7608, -111.8910),
    ("Albuquerque", "NM", 35.0844, -106.6504),
    ("Oklahoma City", "OK", 35.4676, -97.5164),
    ("Kansas City", "MO", 39.0997, -94.5786),
    ("Omaha", "NE", 41.2565, -95.9345),
    ("Milwaukee", "WI", 43.0389, -87.9065),
    ("Indianapolis", "IN", 39.7684, -86.1581),
    ("Louisville", "KY", 38.2527, -85.7585),
    ("New Orleans", "LA", 29.9511, -90.0715),
    ("Tampa", "FL", 27.9506, -82.4572),
    ("Orlando", "FL", 28.5383, -81.3792),
    ("Jacksonville", "FL", 30.3322, -81.6557),
    ("Charleston", "SC", 32.7765, -79.9311),
    ("Richmond", "VA", 37.5407, -77.4360),
    ("Pittsburgh", "PA", 40.4406, -79.9959),
    ("Cleveland", "OH", 41.4993, -81.6944),
    ("Buffalo", "NY", 42.8864, -78.8784),
    ("Hartford", "CT", 41.7658, -72.6734),
    ("Providence", "RI", 41.8240, -71.4128),
    ("Burlington", "VT", 44.4759, -73.2121),
    ("Manchester", "NH", 42.9956, -71.4548),
    ("Spokane", "WA", 47.6588, -117.4260),
    ("Reno", "NV", 39.5296, -119.8138),
    ("Tucson", "AZ", 32.2226, -110.9747),
    ("El Paso", "TX", 31.7619, -106.4850),
    ("San Antonio", "TX", 29.4241, -98.4936),
    ("Birmingham", "AL", 33.5186, -86.8104),
]

SUPPLIER_NAMES = [
    "Northstar Components", "Pioneer Electronics", "Summit Devices", "Blue Ridge Tech",
    "Evergreen Supply Co.", "Sterling Micro Systems", "Cobalt Manufacturing", "Atlas Parts Group",
    "Redwood Technology", "Meridian Electronics", "Granite Peak Components", "Coastal Tech Supply",
    "Ironwood Devices", "Crescent Circuitry", "Frontier Digital", "Keystone Components",
    "Brightline Manufacturing", "Orion Parts Network", "Prairie State Electronics", "Vertex Supply Group",
]

CARRIERS = [
    ("Apex Ground Logistics", "Ground"), ("Continental Parcel", "Ground"),
    ("RapidAir Freight", "Air"), ("BlueLine Transport", "Ground"),
    ("National Express Cargo", "Air"), ("Pioneer LTL", "LTL"),
    ("Summit Freight", "LTL"), ("Coastal Courier", "Ground"),
]


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Approximate straight-line distance; the route factor accounts for roads."""
    from math import asin, cos, radians, sin, sqrt

    earth_miles = 3958.8
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return 2 * earth_miles * asin(sqrt(a))


def build_reference_data(rng: random.Random) -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict]]:
    products = []
    product_categories = list(CATEGORIES)
    for number in range(1, 501):
        category = product_categories[(number - 1) % len(product_categories)]
        product_type = CATEGORIES[category][(number - 1) % len(CATEGORIES[category])]
        products.append({
            "product_id": f"SKU-{number:04d}",
            "product_name": f"{product_type} {number:03d}",
            "category": category,
            "unit_weight_kg": round(rng.uniform(0.08, 18.0), 2),
            "unit_cost_usd": round(rng.uniform(12.0, 1400.0), 2),
            "supplier_id": f"SUP-{(number - 1) % 100 + 1:03d}",
        })

    suppliers = []
    for number in range(1, 101):
        base_name = SUPPLIER_NAMES[(number - 1) % len(SUPPLIER_NAMES)]
        suppliers.append({
            "supplier_id": f"SUP-{number:03d}",
            "supplier_name": f"{base_name} {((number - 1) // len(SUPPLIER_NAMES)) + 1:02d}",
            "supplier_region": rng.choice(["West", "Central", "South", "Northeast"]),
            "lead_time_days": rng.randint(3, 28),
            "on_time_rate": round(rng.uniform(0.86, 0.995), 3),
        })

    warehouses = [
        {"warehouse_id": f"WH-{i:02d}", "warehouse_name": f"Apex {city} Distribution Center",
         "city": city, "state": state, "latitude": lat, "longitude": lon}
        for i, (city, state, lat, lon) in enumerate(WAREHOUSE_SITES, start=1)
    ]

    carriers = [
        {"carrier_id": f"CAR-{i:02d}", "carrier_name": name, "service_type": service,
         "base_cost_usd": round(rng.uniform(18, 55), 2), "cost_per_mile_usd": round(rng.uniform(0.045, 0.14), 3)}
        for i, (name, service) in enumerate(CARRIERS, start=1)
    ]

    routes = []
    for warehouse in warehouses:
        for destination_no, (city, state, lat, lon) in enumerate(DESTINATIONS, start=1):
            miles = haversine_miles(warehouse["latitude"], warehouse["longitude"], lat, lon) * 1.22
            routes.append({
                "route_id": f"RT-{len(routes) + 1:04d}",
                "origin_warehouse_id": warehouse["warehouse_id"],
                "destination_city": city,
                "destination_state": state,
                "distance_miles": round(miles),
                "route_zone": "Local" if miles < 250 else "Regional" if miles < 800 else "National",
            })
    return products, suppliers, warehouses, carriers, routes


def make_shipments(
    rng: random.Random,
    count: int,
    start_date: date,
    products: list[dict],
    suppliers: list[dict],
    warehouses: list[dict],
    carriers: list[dict],
    routes: list[dict],
) -> list[dict]:
    product_by_id = {row["product_id"]: row for row in products}
    supplier_by_id = {row["supplier_id"]: row for row in suppliers}
    warehouse_by_id = {row["warehouse_id"]: row for row in warehouses}
    carrier_by_id = {row["carrier_id"]: row for row in carriers}
    routes_by_warehouse: dict[str, list[dict]] = {}
    for route in routes:
        routes_by_warehouse.setdefault(route["origin_warehouse_id"], []).append(route)

    end_date = start_date + timedelta(days=365) - timedelta(days=1)
    rows = []
    for number in range(1, count + 1):
        product = rng.choice(products)
        supplier = supplier_by_id[product["supplier_id"]]
        warehouse = rng.choice(warehouses)
        route = rng.choice(routes_by_warehouse[warehouse["warehouse_id"]])
        carrier = rng.choice(carriers)
        carrier_details = carrier_by_id[carrier["carrier_id"]]
        order_date = start_date + timedelta(days=rng.randrange((end_date - start_date).days + 1))
        quantity = rng.choices([1, 2, 3, 5, 10, 20], weights=[30, 25, 18, 15, 9, 3])[0]
        weight = product["unit_weight_kg"] * quantity

        service_factor = {"Air": 0.45, "Ground": 1.0, "LTL": 1.15}[carrier_details["service_type"]]
        transit_days = max(1, round(route["distance_miles"] / 430 * service_factor + rng.uniform(0.5, 2.8)))
        estimated_date = order_date + timedelta(days=transit_days)
        # A small share of recent shipments are still moving as of the period end.
        recent_open = (end_date - order_date).days <= 5 and rng.random() < 0.52
        cancelled = rng.random() < 0.015
        actual_date = None
        if cancelled:
            status = "Cancelled"
        elif recent_open:
            status = "In Transit"
        else:
            delay_days = rng.choices([-2, -1, 0, 1, 2, 3, 5, 8], weights=[8, 14, 33, 19, 12, 7, 5, 2])[0]
            actual_date = estimated_date + timedelta(days=delay_days)
            status = "Delayed" if actual_date > estimated_date else "Delivered"

        cost = carrier_details["base_cost_usd"] + route["distance_miles"] * carrier_details["cost_per_mile_usd"]
        cost += weight * rng.uniform(0.18, 0.65)
        if carrier_details["service_type"] == "Air":
            cost *= 1.65
        cost *= rng.uniform(0.92, 1.12)
        rows.append({
            "shipment_id": f"SHP-{number:06d}",
            "order_date": order_date.isoformat(),
            "product_id": product["product_id"],
            "supplier_id": supplier["supplier_id"],
            "warehouse_id": warehouse["warehouse_id"],
            "route_id": route["route_id"],
            "carrier_id": carrier["carrier_id"],
            "quantity": quantity,
            "weight_kg": round(weight, 2),
            "shipping_cost_usd": round(cost, 2),
            "estimated_delivery_date": estimated_date.isoformat(),
            "actual_delivery_date": actual_date.isoformat() if actual_date else "",
            "delivery_delay_days": (actual_date - estimated_date).days if actual_date else "",
            "status": status,
        })
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write an empty CSV: {path}")
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Apex Electronics supply-chain sample CSV data.")
    parser.add_argument("--shipments", type=int, default=10_000, help="number of shipments (default: 10000)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="random seed for repeatable output (default: 42)")
    parser.add_argument("--start-date", type=date.fromisoformat, default=DEFAULT_START_DATE,
                        help="first date in the 12-month period, YYYY-MM-DD (default: 2025-01-01)")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
                        help="where generated CSVs are saved (default: data/simulated)")
    args = parser.parse_args()
    if args.shipments < 1:
        parser.error("--shipments must be at least 1")
    return args


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)
    products, suppliers, warehouses, carriers, routes = build_reference_data(rng)
    shipments = make_shipments(rng, args.shipments, args.start_date, products, suppliers,
                               warehouses, carriers, routes)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    datasets = {
        "shipments.csv": shipments,
        "products.csv": products,
        "suppliers.csv": suppliers,
        "warehouses.csv": warehouses,
        "carriers.csv": carriers,
        "routes.csv": routes,
    }
    for filename, rows in datasets.items():
        write_csv(args.output_dir / filename, rows)

    period_end = args.start_date + timedelta(days=364)
    print(f"Generated {len(shipments):,} shipments for {args.start_date} through {period_end}.")
    print(f"Saved {len(datasets)} CSV files to: {args.output_dir.resolve()}")
    for filename, rows in datasets.items():
        print(f"  {filename}: {len(rows):,} rows")


if __name__ == "__main__":
    main()
