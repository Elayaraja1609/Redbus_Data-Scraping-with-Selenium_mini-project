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
opts.add_argument("--window-size=1920,1080")
opts.add_argument("--disable-http2")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

for label, target in [("SRP", url), ("HOME", "https://www.redbus.in/")]:
    driver.get(target)
    time.sleep(6)
    for sel in ["button[aria-label='Close App Install Banner']", "#btnYes"]:
        for el in driver.find_elements(By.CSS_SELECTOR, sel):
            try:
                driver.execute_script("arguments[0].click();", el)
                time.sleep(0.3)
            except Exception:
                pass
    time.sleep(4)
    inputs = driver.find_elements(By.TAG_NAME, "input")
    print(f"\n=== {label} title={driver.title[:60]} url={driver.current_url[:80]}")
    for inp in inputs[:25]:
        iid = inp.get_attribute("id")
        name = inp.get_attribute("name")
        ph = inp.get_attribute("placeholder")
        if iid or ph or name:
            print(f"  input id={iid} name={name} ph={ph}")
    for s in ["li.clearfix", "li[class*='srp']", "[class*='travels']", "motion.div"]:
        print(f"  {s}: {len(driver.find_elements(By.CSS_SELECTOR, s))}")
    html_path = ROOT / "data" / f"debug_{label.lower()}.html"
    html_path.write_text(driver.page_source, encoding="utf-8")
    print(f"  saved {html_path}")

driver.quit()
