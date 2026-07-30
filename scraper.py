import argparse
import csv
import logging
import math
import random
import re
import sys
import time
from decimal import Decimal, DecimalException, ROUND_HALF_UP
from urllib.parse import urljoin

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Run: pip install requests beautifulsoup4")
    sys.exit(1)

logging.basicConfig(format="%(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

BASE = "https://mdcomputers.in"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": BASE,
}


def clean_price(txt):
    if not txt:
        return ""
    m = re.search(r"\d[\d,]*(?:\.\d{1,2})?", txt)
    if not m:
        return ""
    return m.group(0).replace(",", "")


def get_page(session, url, params=None, retries=3):
    for attempt in range(1, retries + 1):
        try:
            r = session.get(url, params=params, timeout=15)
            r.raise_for_status()

            content_type = r.headers.get("Content-Type", "").lower()
            if content_type and "html" not in content_type:
                raise requests.RequestException(
                    f"unexpected content type: {content_type}"
                )

            return BeautifulSoup(r.text, "html.parser")
        except requests.RequestException as e:
            log.warning("  Attempt %d/%d failed: %s", attempt, retries, e)
            if attempt < retries:
                time.sleep(2 * attempt)
    return None


def check_page_valid(soup):
    title = soup.title.get_text(strip=True).lower() if soup.title else ""
    if any(kw in title for kw in ["captcha", "blocked", "denied", "403", "error"]):
        return False, "bot-check or error page detected"
    return True, "ok"


def scrape_products(soup):
    results = []
    cards = soup.select("div.product-grid-item")

    if not cards:
        cards = soup.select("div.product-wrapper")

    for card in cards:
        item = {}

        link = card.select_one("h3.product-entities-title a")
        if not link:
            link = card.select_one("h3 a, h2 a, h4 a")

        item["name"] = link.get_text(" ", strip=True) if link else "N/A"
        item["url"] = urljoin(BASE, link["href"]) if link and link.get("href") else ""

        img = card.select_one("a.product-image-link img")
        if not img:
            img = card.select_one("img")
        if img:
            src = img.get("src") or img.get("data-src") or ""
            item["image"] = urljoin(BASE, src) if src else ""
        else:
            item["image"] = ""

        old_p = card.select_one("span.del span.amount")
        new_p = card.select_one("span.ins span.amount")
        reg_p = card.select_one("span.price")

        if old_p and new_p:
            item["mrp"] = clean_price(old_p.get_text(" ", strip=True))
            item["price"] = clean_price(new_p.get_text(" ", strip=True))
        elif new_p:
            item["mrp"] = ""
            item["price"] = clean_price(new_p.get_text(" ", strip=True))
        elif reg_p:
            item["mrp"] = ""
            item["price"] = clean_price(reg_p.get_text(" ", strip=True))
        else:
            item["mrp"] = ""
            item["price"] = ""

        badge = card.select_one("span.onsale.product-label")
        if badge:
            item["discount"] = badge.get_text(" ", strip=True)
        elif item["mrp"] and item["price"]:
            try:
                price = Decimal(item["price"])
                mrp = Decimal(item["mrp"])
                if mrp > 0 and Decimal("0") <= price <= mrp:
                    pct = ((Decimal("1") - price / mrp) * Decimal("100")).quantize(
                        Decimal("1"), rounding=ROUND_HALF_UP
                    )
                    item["discount"] = f"-{pct}%"
                else:
                    item["discount"] = ""
            except DecimalException:
                item["discount"] = ""
        else:
            item["discount"] = ""

        if item["name"] == "N/A" and not item["url"]:
            continue

        results.append(item)

    return results


def dump_csv(data, path):
    cols = ["name", "price", "mrp", "discount", "url", "image"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(data)


def show(items):
    for i, p in enumerate(items, 1):
        log.info(f"\n[{i}] {p['name']}")
        if p["price"]:
            line = f"    Rs.{p['price']}"
            if p["mrp"]:
                line += f" (MRP: Rs.{p['mrp']})"
            if p["discount"]:
                line += f" [{p['discount']}]"
            log.info(line)
        if p["url"]:
            log.info("    %s", p['url'])


def run(term, max_pages=10, out=None, delay=1.5):
    term = term.strip()
    if not term:
        raise ValueError("search term cannot be empty")
    if max_pages < 1:
        raise ValueError("max_pages must be at least 1")
    if delay < 0:
        raise ValueError("delay must be zero or greater")

    with requests.Session() as session:
        session.headers.update(HEADERS)
        return _scrape_loop(session, term, max_pages, out, delay)


def _scrape_loop(session, term, max_pages, out, delay):
    all_items = []
    seen = set()
    failed_pages = []

    log.info('Searching "%s"...\n', term)

    for pg in range(1, max_pages + 1):
        if pg > 1 and delay > 0:
            time.sleep(random.uniform(delay * 0.8, delay * 1.3))

        params = {
            "route": "product/search",
            "search": term,
            "page": pg,
        }
        soup = get_page(session, BASE, params=params)

        if soup is None:
            failed_pages.append(pg)
            continue

        valid, status = check_page_valid(soup)
        if not valid:
            log.warning("  pg %d -> %s; stopping", pg, status)
            break

        prods = scrape_products(soup)

        if not prods:
            log.info("  pg %d -> no items; stopping", pg)
            break

        added = 0
        for item in prods:
            key = item["url"]
            if not key:
                key = (item["name"], item["price"], item["image"])
            if key not in seen:
                seen.add(key)
                all_items.append(item)
                added += 1

        log.info("  pg %d -> %d found, %d new", pg, len(prods), added)

        if added == 0:
            log.info("  pg %d -> no new products; stopping", pg)
            break

    if failed_pages:
        log.warning("\n  Pages that failed to load: %s", failed_pages)

    log.info("\nTotal unique products: %d", len(all_items))
    show(all_items)

    if out:
        dump_csv(all_items, out)
        log.info("\nSaved to %s", out)

    return all_items


def positive_int(val):
    try:
        n = int(val)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if n < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return n


def nonnegative_float(val):
    try:
        n = float(val)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if not math.isfinite(n):
        raise argparse.ArgumentTypeError("must be a finite number")
    if n < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return n


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Product scraper")
    ap.add_argument("term", nargs="?", default="external harddrive", help="what to search")
    ap.add_argument("--pages", type=positive_int, default=10, help="max pages (default: 10)")
    ap.add_argument("-o", "--output", help="csv output file")
    ap.add_argument("--delay", type=nonnegative_float, default=1.5, help="delay between requests in seconds (default: 1.5)")
    ap.add_argument("-v", "--verbose", action="store_true", help="enable debug output")
    args = ap.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.output:
        slug = re.sub(r"\W+", "_", args.term).strip("_").lower() or "products"
        args.output = f"results_{slug}.csv"

    try:
        run(args.term, args.pages, args.output, args.delay)
    except (ValueError, OSError) as exc:
        log.error("Error: %s", exc)
        sys.exit(1)
