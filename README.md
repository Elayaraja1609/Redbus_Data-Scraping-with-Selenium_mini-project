# Redbus Data Scraping with Selenium

A Python mini-project that scrapes bus listings from [redbus.in](https://www.redbus.in/), stores them in **SQLite** or **MySQL**, and explores the data through a **Streamlit** dashboard with dynamic filters and charts.

## Features

- **Automated scraping** with Selenium and Chrome (ChromeDriver managed via `webdriver-manager`)
- **Direct URL navigation** to search results, with fallback to the homepage search form (`#srcinput`, `#destinput`)
- **Structured storage** of bus name, type, departure/arrival times, duration, rating, price, and seat availability
- **Government bus detection** using state transport keywords (TNSTC, SETC, KSRTC, APSRTC, etc.)
- **Streamlit dashboard** with filters for route, bus type, price, rating, seats, government-only, and name search
- **Charts** — price histogram and rating box plots (Plotly)
- **CSV export** of filtered results
- **Dual database support** — SQLite (default) or MySQL

## Tech Stack

| Layer | Tools |
|-------|--------|
| Scraping | Selenium 4, Chrome, webdriver-manager |
| Storage | SQLite / MySQL |
| Dashboard | Streamlit, Pandas, Plotly |
| Config | python-dotenv |

## Prerequisites

- **Python 3.10+**
- **Google Chrome** (latest stable)
- **MySQL 8+** (optional — only if `DB_ENGINE=mysql`)

## Quick Start

```bash
cd MiniProject2
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
copy .env.example .env          # Windows
# cp .env.example .env          # macOS / Linux
```

Initialize the database and scrape default routes:

```bash
python run_scraper.py --init-db
python run_scraper.py --no-headless
```

Launch the dashboard:

```bash
streamlit run app/streamlit_app.py
```

## Configuration

Copy `.env.example` to `.env` and adjust as needed:

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_ENGINE` | `sqlite` | `sqlite` or `mysql` |
| `MYSQL_HOST` | `localhost` | MySQL host |
| `MYSQL_PORT` | `3306` | MySQL port |
| `MYSQL_USER` | `root` | MySQL user |
| `MYSQL_PASSWORD` | — | MySQL password |
| `MYSQL_DATABASE` | `redbus_db` | Database name |
| `SCRAPE_DATE` | tomorrow | Travel date (`DD-Mon-YYYY`, e.g. `20-May-2026`) |
| `HEADLESS` | `true` | Run Chrome headless (`true` / `false`) |
| `MAX_BUSES_PER_ROUTE` | `40` | Max listings saved per route |

**SQLite (default):** data is stored at `data/redbus.db`.

**MySQL:** set `DB_ENGINE=mysql`, provide credentials, then run `python run_scraper.py --init-db`.

## Scraper Usage

```bash
# Create schema only
python run_scraper.py --init-db

# Scrape all default routes (see src/config.py)
python run_scraper.py

# Single route with visible browser (recommended on Windows)
python run_scraper.py --from Chennai --to Bangalore --no-headless

# Custom travel date
python run_scraper.py --date 25-May-2026 --no-headless
```

### Default routes

| From | To |
|------|-----|
| Chennai | Bangalore |
| Chennai | Coimbatore |
| Chennai | Madurai |
| Bangalore | Mysore |
| Hyderabad | Vijayawada |
| Chennai | Trichy |

Edit `DEFAULT_ROUTES` in `src/config.py` to change these.

## Streamlit Dashboard

```bash
streamlit run app/streamlit_app.py
```

**Sidebar filters:** route, bus type, price range, minimum star rating, minimum seats, government/state transport only, bus name search.

**Main view:** summary metrics, price/rating charts, sortable table, and CSV download.

## Project Structure

```
MiniProject2/
├── app/
│   └── streamlit_app.py    # Streamlit UI
├── src/
│   ├── config.py           # Routes, env, government keywords
│   ├── scraper.py          # Selenium scraper
│   └── db.py               # DB init, inserts, filtered queries
├── sql/
│   ├── schema.sql          # MySQL schema
│   └── sample_queries.sql  # Example SQL
├── scripts/
│   ├── probe_redbus.py     # Save SRP HTML for selector debugging
│   └── debug_inputs.py     # List input fields on home / SRP pages
├── data/
│   ├── redbus.db           # SQLite database (gitignored)
│   ├── screenshots/        # Error screenshots (gitignored)
│   └── debug_*.html        # Saved page snapshots for DOM inspection
├── run_scraper.py          # CLI entry point
├── requirements.txt
└── .env.example
```

## Database Schema

Table: `bus_routes`

| Column | Description |
|--------|-------------|
| `route_name` | e.g. `Chennai to Bangalore` |
| `route_link` | Search results URL |
| `busname` | Operator / travels name |
| `bustype` | AC, Sleeper, Seater, etc. |
| `departing_time` | Departure time |
| `duration` | Journey duration |
| `reaching_time` | Arrival time |
| `star_rating` | User rating (0–5) |
| `price` | Fare in ₹ |
| `seats_available` | Available seats |
| `is_government` | `1` if state transport keyword matched |
| `scraped_at` | Timestamp |

## Helper Scripts

```bash
# Save search-results page HTML to data/debug_page.html
python scripts/probe_redbus.py

# Print input IDs and listing selectors on home + SRP
python scripts/debug_inputs.py
```

## Troubleshooting

| Issue | Suggestion |
|-------|------------|
| `ERR_HTTP2_PROTOCOL_ERROR` or blank page | Use **`--no-headless`** on Windows; scraper also passes `--disable-http2` |
| 0 buses scraped | Redbus DOM may have changed — run `probe_redbus.py`, update selectors in `src/scraper.py` (`tupleWrapper`, `travelsName`, `finalFare`, etc.) |
| Few government buses | Use routes with TNSTC/SETC/KSRTC (intra-state) or filter RTC on the live site before scraping |
| Empty Streamlit app | Run `python run_scraper.py` first to populate the database |
| Chrome / driver errors | Update Chrome; delete cached driver and re-run (webdriver-manager will re-download) |

On scrape errors, screenshots are saved under `data/screenshots/`.

## Requirements

```
selenium>=4.15.0
webdriver-manager>=4.0.0
streamlit>=1.28.0
pandas>=2.0.0
mysql-connector-python>=8.2.0
python-dotenv>=1.0.0
plotly>=5.18.0
```

Install with: `pip install -r requirements.txt`

## License

Educational mini-project — use responsibly and respect [redbus.in](https://www.redbus.in/) terms of service. Scraping frequency should be kept low; this tool is intended for learning and analysis.
