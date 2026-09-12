import argparse
import threading
import time
from decimal import Decimal, InvalidOperation
from typing import Optional

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template_string, request


app = Flask(__name__)
MONITOR_STATE = {
    "url": "",
    "interval": 300,
    "running": False,
    "status": "idle",
    "last_price": None,
    "last_checked": None,
}


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/")
def index():
    return render_template_string(
        '''
        <!doctype html>
        <html>
        <head>
            <title>Amazon Price Monitor</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 760px; margin: 40px auto; padding: 24px; }
                label { display: block; margin-bottom: 8px; font-weight: bold; }
                input, button { font-size: 16px; padding: 10px 12px; }
                input { width: 100%; box-sizing: border-box; margin-bottom: 12px; }
                button { cursor: pointer; width: 100%; }
                .card { border: 1px solid #ddd; border-radius: 10px; padding: 20px; background: #fafafa; }
                .status { margin-top: 18px; padding: 12px; background: #eef6ff; border-radius: 8px; }
                .tiny { color: #555; font-size: 13px; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>Amazon Price Monitor</h1>
                <form id="monitor-form">
                    <label for="url">Amazon product URL</label>
                    <input id="url" name="url" type="url" placeholder="https://www.amazon.com/..." required />

                    <label for="interval">Check every (seconds)</label>
                    <input id="interval" name="interval" type="number" value="300" min="30" step="30" required />

                    <button type="submit">Start monitoring</button>
                </form>

                <div class="status" id="status-box">Idle. Paste a URL and start monitoring.</div>
                <div class="tiny" id="meta-box"></div>
            </div>

            <script>
                const statusBox = document.getElementById('status-box');
                const metaBox = document.getElementById('meta-box');

                async function loadStatus() {
                    const response = await fetch('/status');
                    const data = await response.json();
                    const priceText = data.last_price !== null ? '$' + data.last_price : 'No price yet';
                    statusBox.textContent = data.status + ' | Current price: ' + priceText;
                    metaBox.textContent = data.url ? 'URL: ' + data.url + ' | Check interval: ' + data.interval + 's' : 'No active monitor';
                }

                document.getElementById('monitor-form').addEventListener('submit', async (event) => {
                    event.preventDefault();
                    const form = new FormData(event.target);
                    const response = await fetch('/start', {
                        method: 'POST',
                        body: form,
                    });
                    const data = await response.json();
                    statusBox.textContent = data.status;
                    loadStatus();
                });

                setInterval(loadStatus, 5000);
                loadStatus();
            </script>
        </body>
        </html>
        '''
    )


@app.get("/status")
def status():
    return jsonify({
        "url": MONITOR_STATE["url"],
        "interval": MONITOR_STATE["interval"],
        "running": MONITOR_STATE["running"],
        "status": MONITOR_STATE["status"],
        "last_price": str(MONITOR_STATE["last_price"]) if MONITOR_STATE["last_price"] is not None else None,
        "last_checked": MONITOR_STATE["last_checked"],
    })


@app.post("/start")
def start_monitoring():
    url = request.form.get("url", "").strip()
    interval = int(request.form.get("interval", "300") or "300")
    if not url:
        return jsonify({"status": "URL is required."}), 400

    MONITOR_STATE["url"] = url
    MONITOR_STATE["interval"] = max(interval, 30)
    MONITOR_STATE["status"] = "Monitoring started"
    MONITOR_STATE["running"] = True

    thread = threading.Thread(target=run_monitor_loop, args=(url, MONITOR_STATE["interval"]), daemon=True)
    thread.start()
    return jsonify({"status": f"Monitoring started for {url} every {MONITOR_STATE['interval']} seconds."})


def run_monitor_loop(url: str, interval_seconds: int) -> None:
    last_price: Optional[Decimal] = None
    while MONITOR_STATE["running"] and MONITOR_STATE["url"] == url:
        try:
            price = fetch_price(url)
            MONITOR_STATE["last_checked"] = time.strftime("%Y-%m-%d %H:%M:%S")
            if price is None:
                MONITOR_STATE["status"] = "Price not found"
            else:
                if last_price is None:
                    MONITOR_STATE["status"] = f"Current price: ${price}"
                elif price != last_price:
                    MONITOR_STATE["status"] = f"Price changed: ${last_price} -> ${price}"
                else:
                    MONITOR_STATE["status"] = f"Current price: ${price}"
                last_price = price
                MONITOR_STATE["last_price"] = price
        except Exception as exc:  # pragma: no cover - runtime path
            MONITOR_STATE["status"] = f"Error: {exc}"
            MONITOR_STATE["last_checked"] = time.strftime("%Y-%m-%d %H:%M:%S")

        time.sleep(interval_seconds)


def extract_price(html: str) -> Optional[Decimal]:
    """Extract the product price from an Amazon product HTML page."""
    soup = BeautifulSoup(html, "html.parser")

    meta_amount = soup.select_one('meta[property="og:price:amount"]')
    if meta_amount and meta_amount.get("content"):
        try:
            return Decimal(meta_amount["content"].strip())
        except InvalidOperation:
            pass

    for selector in [
        "#priceblock_ourprice",
        "#price_inside_buybox",
        "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
        "#corePrice_feature_div .a-price .a-offscreen",
        ".a-price .a-offscreen",
        ".a-price-whole",
    ]:
        node = soup.select_one(selector)
        if not node:
            continue

        text = node.get_text(" ", strip=True)
        cleaned = text.replace("$", "").replace(",", "").strip()
        if not cleaned:
            continue
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            continue

    return None


def fetch_price(url: str) -> Optional[Decimal]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    return extract_price(response.text)


def monitor(url: str, interval_seconds: int = 300, verbose: bool = True) -> None:
    last_price: Optional[Decimal] = None
    print(f"Monitoring: {url}")
    print(f"Checking every {interval_seconds} seconds")

    while True:
        try:
            price = fetch_price(url)
        except Exception as exc:  # pragma: no cover - runtime path
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error: {exc}")
            time.sleep(interval_seconds)
            continue

        if price is None:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Price not found on page")
        else:
            if last_price is None:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Current price: ${price}")
            elif price != last_price:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Price changed: ${last_price} -> ${price}")
            elif verbose:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Current price: ${price}")
            last_price = price

        time.sleep(interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor an Amazon product price until it changes.")
    parser.add_argument("url", nargs="?", help="Amazon product URL to monitor")
    parser.add_argument("--interval", type=int, default=300, help="Seconds between checks (default: 300)")
    parser.add_argument("--quiet", action="store_true", help="Only print changes and errors")
    parser.add_argument("--web", action="store_true", help="Start the local web UI instead of CLI monitoring")
    parser.add_argument("--host", default="127.0.0.1", help="Host for the web UI")
    parser.add_argument("--port", type=int, default=5000, help="Port for the web UI")
    args = parser.parse_args()

    if args.web:
        app.run(host=args.host, port=args.port, debug=False)
        return

    if not args.url:
        parser.error("a URL is required unless --web is used")

    monitor(args.url, interval_seconds=args.interval, verbose=not args.quiet)


if __name__ == "__main__":
    main()
