from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Optional
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from src.config import (
    DATA_DIR,
    DEFAULT_ROUTES,
    HEADLESS,
    MAX_BUSES_PER_ROUTE,
    REDBUS_BASE_URL,
    SCRAPE_DATE,
)
from src.db import Database, is_government_bus

RESULTS_WAIT_SELECTORS = (
    "li[class*='tupleWrapper']",
    "[class*='travelsName']",
    "li.clearfix.row-sec",
    "li.clearfix",
)

CARD_SELECTORS = (
    "li[class*='tupleWrapper']",
    "li.clearfix.row-sec",
    "li.clearfix",
)


def _slugify_city(city: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-")


def _build_search_url(route: "RouteConfig", travel_date: str) -> str:
    slug = f"{_slugify_city(route.from_city)}-to-{_slugify_city(route.to_city)}"
    return f"{REDBUS_BASE_URL}bus-tickets/{slug}?onward={travel_date}"


@dataclass
class RouteConfig:
    from_city: str
    to_city: str

    @property
    def route_name(self) -> str:
        return f"{self.from_city} to {self.to_city}"


def _parse_price(text: str) -> Optional[float]:
    if not text:
        return None
    match = re.search(r"[\d,]+(?:\.\d+)?", text.replace(",", ""))
    return float(match.group()) if match else None


def _parse_rating(text: str) -> Optional[float]:
    if not text:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if match:
        val = float(match.group(1))
        return val if val <= 5 else None
    return None


def _parse_seats(text: str) -> Optional[int]:
    if not text:
        return None
    match = re.search(r"(\d+)\s*seat", text, re.I)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else None


def _normalize_time(value: str) -> Optional[str]:
    """Return HH:MM:SS for SQL TIME columns."""
    if not value:
        return None
    value = value.strip().upper()
    for fmt in ("%H:%M", "%I:%M %p", "%I:%M%p"):
        try:
            from datetime import datetime

            return datetime.strptime(value.replace(" ", ""), fmt.replace(" ", "")).strftime(
                "%H:%M:%S"
            )
        except ValueError:
            continue
    match = re.search(r"(\d{1,2}):(\d{2})\s*(AM|PM)?", value, re.I)
    if not match:
        return value[:8] if len(value) <= 8 else None
    hour, minute, ampm = int(match.group(1)), match.group(2), match.group(3)
    if ampm and ampm.upper() == "PM" and hour < 12:
        hour += 12
    if ampm and ampm.upper() == "AM" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute}:00"


class RedbusScraper:
    def __init__(self, headless: bool = HEADLESS) -> None:
        self.headless = headless
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None

    def _build_driver(self) -> webdriver.Chrome:
        options = Options()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-http2")
        options.add_argument("--ignore-certificate-errors")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.implicitly_wait(2)
        return driver

    def start(self) -> None:
        self.driver = self._build_driver()
        self.wait = WebDriverWait(self.driver, 45)

    def stop(self) -> None:
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.wait = None

    def __enter__(self) -> "RedbusScraper":
        self.start()
        return self

    def __exit__(self, *args: Any) -> None:
        self.stop()

    def _js_click(self, element: Any) -> None:
        assert self.driver
        self.driver.execute_script("arguments[0].click();", element)

    def _dismiss_overlays(self) -> None:
        assert self.driver
        selectors = [
            "button[aria-label='Close App Install Banner']",
            "button#btnYes",
            "#close_button",
            "button[aria-label='Close']",
            "button[class*='close']",
        ]
        for sel in selectors:
            for el in self.driver.find_elements(By.CSS_SELECTOR, sel):
                try:
                    if el.is_displayed():
                        self._js_click(el)
                        time.sleep(0.4)
                except Exception:
                    continue

    def _save_debug(self, route: RouteConfig, tag: str) -> None:
        assert self.driver
        out_dir = DATA_DIR / "screenshots"
        out_dir.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^\w-]+", "_", route.route_name)
        path = out_dir / f"{safe}_{tag}.png"
        try:
            self.driver.save_screenshot(str(path))
            print(f"  Debug screenshot: {path}")
        except Exception:
            pass

    def _scroll_results(self) -> None:
        assert self.driver
        last_count = 0
        for _ in range(10):
            self.driver.execute_script("window.scrollBy(0, 1200);")
            time.sleep(1.0)
            count = len(self.driver.find_elements(By.CSS_SELECTOR, CARD_SELECTORS[0]))
            if count == last_count and count > 0:
                break
            last_count = count
        self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)

    def _wait_for_results(self) -> None:
        assert self.driver and self.wait
        combined = ", ".join(RESULTS_WAIT_SELECTORS)
        try:
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, combined))
            )
        except TimeoutException as exc:
            raise RuntimeError("Bus listing page did not load in time") from exc

    def _fill_autocomplete(self, input_selectors: list[str], city: str) -> None:
        assert self.driver and self.wait
        input_el = None
        for sel in input_selectors:
            try:
                input_el = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
                break
            except TimeoutException:
                continue
        if not input_el:
            raise RuntimeError(f"Could not find city input for {city}")

        input_el.clear()
        input_el.send_keys(city)
        time.sleep(1.2)
        input_el.send_keys(Keys.ARROW_DOWN)
        input_el.send_keys(Keys.ENTER)
        time.sleep(0.8)

    def _set_date(self, travel_date: str) -> None:
        assert self.driver
        try:
            date_input = self.driver.find_element(By.ID, "onward_cal")
            date_input.click()
            time.sleep(0.8)
        except NoSuchElementException:
            return

        # Try clicking a date cell containing the day number
        day_match = re.search(r"(\d{1,2})", travel_date)
        if day_match:
            day = day_match.group(1).lstrip("0") or day_match.group(1)
            xpath_variants = [
                f"//td[contains(@class,'day') and normalize-space(text())='{day}']",
                f"//span[contains(@class,'day') and text()='{day}']",
            ]
            for xpath in xpath_variants:
                try:
                    cell = self.driver.find_element(By.XPATH, xpath)
                    cell.click()
                    return
                except NoSuchElementException:
                    continue

    def _click_search(self) -> None:
        assert self.driver and self.wait
        for sel in ["#search_button", "button.search-btn", "button[id*='search']"]:
            try:
                btn = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
                btn.click()
                return
            except TimeoutException:
                continue
        raise RuntimeError("Search button not found")

    def _open_search_results(self, route: RouteConfig, travel_date: str) -> str:
        """Navigate to SRP via direct URL; fall back to homepage search form."""
        assert self.driver and self.wait
        search_url = _build_search_url(route, travel_date)
        self.driver.get(search_url)
        time.sleep(6)
        self._dismiss_overlays()
        time.sleep(2)

        if "bus-tickets" in self.driver.current_url and "can't be reached" not in self.driver.title.lower():
            try:
                self._wait_for_results()
                return self.driver.current_url
            except RuntimeError:
                print("  Direct URL loaded but no listings yet, trying homepage form...")

        self.driver.get(REDBUS_BASE_URL)
        time.sleep(2)
        self._dismiss_overlays()
        self._fill_autocomplete(
            [
                "#srcinput",
                "#src",
                "input#src",
                "input[placeholder*='From']",
                "input[data-placeholder*='From']",
            ],
            route.from_city,
        )
        self._fill_autocomplete(
            [
                "#destinput",
                "#dest",
                "input#dest",
                "input[placeholder*='To']",
                "input[data-placeholder*='To']",
            ],
            route.to_city,
        )
        self._set_date(travel_date)
        self._click_search()
        self._wait_for_results()
        return self.driver.current_url

    def scrape_route(
        self, route: RouteConfig, travel_date: str = SCRAPE_DATE
    ) -> list[dict[str, Any]]:
        assert self.driver and self.wait
        try:
            route_link = self._open_search_results(route, travel_date)
            time.sleep(2)
            self._dismiss_overlays()
            self._scroll_results()
            records = self._parse_listings(route, route_link)
            if not records:
                self._save_debug(route, "no_results")
            return records
        except Exception:
            self._save_debug(route, "error")
            raise

    def _parse_listings(self, route: RouteConfig, route_link: str) -> list[dict[str, Any]]:
        assert self.driver
        records: list[dict[str, Any]] = []
        cards: list[Any] = []
        for sel in CARD_SELECTORS:
            found = self.driver.find_elements(By.CSS_SELECTOR, sel)
            if len(found) >= 3:
                cards = found
                break
        if not cards:
            for sel in CARD_SELECTORS:
                found = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if found:
                    cards = found
                    break

        for card in cards[:MAX_BUSES_PER_ROUTE]:
            try:
                record = self._parse_card(card, route, route_link)
                if record and record.get("busname"):
                    records.append(record)
            except Exception:
                continue
        return records

    def _parse_card(
        self, card: Any, route: RouteConfig, route_link: str
    ) -> Optional[dict[str, Any]]:
        text_blob = card.text or ""

        busname = self._first_text(
            card,
            [
                "[class*='travelsName']",
                ".travels",
                "p.travels",
                "[class*='travels']",
                ".bus-name",
            ],
        )
        if not busname:
            lines = [ln.strip() for ln in text_blob.split("\n") if ln.strip()]
            busname = lines[0] if lines else ""

        bustype = self._first_text(
            card,
            ["[class*='busType']", ".bus-type", "motion.div.bus-type", "[class*='bus-type']"],
        )
        if not bustype:
            bustype = self._infer_bustype(text_blob)

        dep = self._first_text(
            card, ["[class*='boardingTime']", ".dp-time", "[class*='dp-time']"]
        )
        arr = self._first_text(
            card, ["[class*='droppingTime']", ".bp-time", "[class*='bp-time']"]
        )
        duration = self._first_text(
            card,
            [
                "p[class*='duration___']",
                "[class*='duration___']",
                ".dur",
                "[class*='duration']",
            ],
        )
        price_text = self._first_text(
            card,
            [
                "[class*='finalFare']",
                "[class*='tupleFare']",
                ".fare",
                "[class*='fare']",
            ],
        )
        rating_text = self._first_text(
            card,
            [
                "[class*='ratingTag']",
                "[class*='rating___']",
                ".rating",
                "[class*='rating']",
            ],
        )
        seats_text = self._first_text(
            card,
            [
                "[class*='totalSeats']",
                "[class*='seatsWrap']",
                ".seat-left",
                "[class*='seat-left']",
            ],
        )

        if not dep:
            times = re.findall(r"\b\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?\b", text_blob)
            dep = times[0] if times else None
            arr = times[1] if len(times) > 1 else arr

        price = _parse_price(price_text or text_blob)
        rating = _parse_rating(rating_text or text_blob)
        seats = _parse_seats(seats_text or text_blob)

        return {
            "route_name": route.route_name,
            "route_link": route_link,
            "busname": busname.strip(),
            "bustype": (bustype or "Unknown").strip(),
            "departing_time": _normalize_time(dep) if dep else None,
            "duration": (duration or self._extract_duration(text_blob)).strip()
            if duration or self._extract_duration(text_blob)
            else None,
            "reaching_time": _normalize_time(arr) if arr else None,
            "star_rating": rating,
            "price": price,
            "seats_available": seats,
            "is_government": is_government_bus(busname),
        }

    @staticmethod
    def _first_text(parent: Any, selectors: list[str]) -> str:
        for sel in selectors:
            try:
                el = parent.find_element(By.CSS_SELECTOR, sel)
                txt = (el.text or "").strip()
                if txt:
                    return txt
            except NoSuchElementException:
                continue
        return ""

    @staticmethod
    def _infer_bustype(text: str) -> str:
        upper = text.upper()
        parts = []
        for label in ("SLEEPER", "SEATER", "A/C", "AC", "NON-AC", "NON AC"):
            if label in upper:
                parts.append(label.replace("A/C", "AC"))
        return " / ".join(dict.fromkeys(parts)) if parts else "Unknown"

    @staticmethod
    def _extract_duration(text: str) -> str:
        match = re.search(
            r"(\d+h\s*\d*m|\d+\s*hr[s]?\s*\d*\s*min[s]?|\d+:\d+\s*hrs?)",
            text,
            re.I,
        )
        return match.group(1) if match else ""


def scrape_routes(
    routes: Optional[list[dict[str, str]]] = None,
    travel_date: str = SCRAPE_DATE,
    save: bool = True,
    db: Optional[Database] = None,
) -> list[dict[str, Any]]:
    """Scrape configured routes and optionally persist to database."""
    route_list = [RouteConfig(**r) for r in (routes or DEFAULT_ROUTES)]
    db = db or Database()
    all_records: list[dict[str, Any]] = []

    with RedbusScraper() as scraper:
        for route in route_list:
            print(f"Scraping {route.route_name} ({travel_date})...")
            try:
                records = scraper.scrape_route(route, travel_date)
                print(f"  Found {len(records)} buses")
                if save and records:
                    db.clear_route(route.route_name)
                    db.insert_buses(records)
                all_records.extend(records)
            except Exception as exc:
                print(f"  Failed: {exc}")
            time.sleep(2)

    gov_count = sum(1 for r in all_records if r.get("is_government"))
    print(f"Total: {len(all_records)} buses ({gov_count} government/state)")
    return all_records


if __name__ == "__main__":
    scrape_routes()
