# Apex Supply Chain Intelligence

A beginner-friendly supply-chain analytics project using fictional shipment data, Python, MySQL, and Streamlit.

## What it does

- Generates 10,000 fictional shipments covering January through December 2025.
- Validates shipment IDs, lookup references, dates, statuses, and costs.
- Loads reference data and shipments into SQLite and, when configured, MySQL.
- Calculates monthly carrier delivery and shipping-cost metrics.
- Displays shipment and carrier trends in an interactive Streamlit dashboard.

## Run locally

From the project folder, install the packages and generate/load the data:

```powershell
python -m pip install -r requirements.txt
python pipeline.py
python -m streamlit run app.py
```

The pipeline always creates a local SQLite database. To also load MySQL, create the `apex_supply_chain` database, run the account setup statements in `mysql_setup.sql` from MySQL Workbench, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, and enter the local MySQL account settings there. Never commit `secrets.toml` or your database password.

## Deploy a demo dashboard

The repository includes only fictional CSV sample data. Without local MySQL credentials or a local SQLite database, the app reads those CSVs and calculates the monthly carrier summaries in memory. This lets a hosted demo display the dashboard without connecting to your home MySQL server.

For Streamlit Community Cloud, push this project to GitHub, create an app using `app.py` as the entrypoint, and let Streamlit install packages from `requirements.txt`. Do not upload `.streamlit/secrets.toml`. The hosted demo uses the included CSV snapshot; your local MySQL database stays on your computer.

## Project files

- `data_generator.py` creates the fictional CSV source data.
- `pipeline.py` coordinates generation, validation, and database loading.
- `mysql_writer.py` creates and loads MySQL tables and monthly carrier summaries.
- `db_config.py` reads local MySQL settings from the ignored secrets file.
- `app.py` reads the data and displays the interactive dashboard.
- `data/simulated/` contains the sample CSV files used by the hosted demo.
