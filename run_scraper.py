from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.config import DEFAULT_ROUTES, SCRAPE_DATE
from src.db import Database, init_db
from src.scraper import scrape_routes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape Redbus bus data")
    parser.add_argument("--init-db", action="store_true", help="Create database schema only")
    parser.add_argument("--date", default=SCRAPE_DATE, help="Travel date (e.g. 20-May-2026)")
    parser.add_argument("--from", dest="from_city", help="Source city")
    parser.add_argument("--to", dest="to_city", help="Destination city")
    parser.add_argument("--no-headless", action="store_true", help="Show browser window")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.init_db:
        init_db()
        return

    if not args.from_city:
        init_db()
    routes = None
    if args.from_city and args.to_city:
        routes = [{"from_city": args.from_city, "to_city": args.to_city}]

    if args.no_headless:
        import src.config as cfg

        cfg.HEADLESS = False

    scrape_routes(routes=routes, travel_date=args.date)
    stats = Database().get_stats()
    print("Database stats:", stats)


if __name__ == "__main__":
    main()
