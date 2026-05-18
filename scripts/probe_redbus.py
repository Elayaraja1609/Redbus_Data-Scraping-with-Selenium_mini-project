import time
from datetime import date, timedelta
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

ROOT = Path(__file__).resolve().parent.parent
d = (date.today() + timedelta(days=1)).strftime("%d-%b-%Y")
url = f"https://www.redbus.in/bus-tickets/chennai-to-bangalore?onward={d}"

opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1920,1080")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
driver.get(url)
time.sleep(5)

for sel in [
    "button[aria-label='Close App Install Banner']",
    "#btnYes",
    "button[aria-label='Close']",
]:
    for el in driver.find_elements(By.CSS_SELECTOR, sel):
        try:
            driver.execute_script("arguments[0].click();", el)
            time.sleep(0.3)
        except Exception:
            pass

time.sleep(4)
selectors = [
    "li.clearfix.row-sec",
    "li.clearfix",
    "div[data-testid]",
    "ul.search-results li",
    "li[class*='srp']",
    "div[class*='srp']",
    "[class*='bus-item']",
    "[class*='BusItem']",
    "li[id*='bus']",
]
for s in selectors:
    n = len(driver.find_elements(By.CSS_SELECTOR, s))
    if n:
        print(f"{s}: {n}")

print("title:", driver.title[:100])
print("url:", driver.current_url)

out = ROOT / "data" / "debug_page.html"
out.parent.mkdir(exist_ok=True)
out.write_text(driver.page_source, encoding="utf-8")
print("saved", out, "len", len(driver.page_source))
driver.quit()
