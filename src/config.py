import os
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = PROJECT_ROOT / "sql"
DATA_DIR = PROJECT_ROOT / "data"
SQLITE_PATH = DATA_DIR / "redbus.db"

REDBUS_BASE_URL = "https://www.redbus.in/"

MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "redbus_db"),
}

USE_MYSQL = os.getenv("DB_ENGINE", "sqlite").lower() == "mysql"
HEADLESS = os.getenv("HEADLESS", "true").lower() in ("1", "true", "yes")
MAX_BUSES_PER_ROUTE = int(os.getenv("MAX_BUSES_PER_ROUTE", "40"))

_scrape_date = os.getenv("SCRAPE_DATE", "").strip()
SCRAPE_DATE = _scrape_date if _scrape_date else (date.today() + timedelta(days=1)).strftime("%d-%b-%Y")

# Default routes: mix of state transport + private operators
DEFAULT_ROUTES = [
    {"from_city": "Chennai", "to_city": "Bangalore"},
    {"from_city": "Chennai", "to_city": "Coimbatore"},
    {"from_city": "Chennai", "to_city": "Madurai"},
    {"from_city": "Bangalore", "to_city": "Mysore"},
    {"from_city": "Hyderabad", "to_city": "Vijayawada"},
    {"from_city": "Chennai", "to_city": "Trichy"},
]

# Government / state transport name fragments (Redbus listings)
GOVERNMENT_BUS_KEYWORDS = (
    "TNSTC", "SETC", "KSRTC", "APSRTC", "TGSRTC", "TSRTC", "MSRTC", "RSRTC",
    "UPSRTC", "OSRTC", "KRTC", "PEPSU", "HRTC", "JKSRTC", "WBTC", "GSRTC",
    "Kerala RTC", "KRTC", "CTU", "PUNBUS", "Haryana Roadways", "Delhi Transport",
    "BMTC", "DTC", "RTC", "Road Transport", "State Express", "State Transport",
)
