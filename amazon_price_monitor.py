import argparse
import json
import threading
import time
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template_string, request


app = Flask(__name__)
HISTORY_FILE = Path(__file__).with_name("price_history.json")
MONITOR_STATE = {
    "url": "",
    "interval": 300,
    "running": False,
    "status": "idle",
    "last_price": None,
    "last_checked": None,
    "history": [],
}


def load_history() -> list[dict[str, Any]]:
    if not HISTORY_FILE.exists():
        return []
    try:
        with HISTORY_FILE.open("r", encoding="utf-8") as file_handle:
            data = json.load(file_handle)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_history(history: list[dict[str, Any]]) -> None:
    try:
        with HISTORY_FILE.open("w", encoding="utf-8") as file_handle:
            json.dump(history, file_handle, indent=2)
    except OSError:
        pass


def get_history_for_days(history: list[dict[str, Any]], days: int) -> list[dict[str, Any]]:
    if days <= 0:
        return []

    cutoff = datetime.now() - timedelta(days=days)
    recent = []
    for item in history:
        checked_at = item.get("checked_at")
        if not checked_at:
            continue
        try:
            dt = datetime.strptime(str(checked_at), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        if dt >= cutoff:
            recent.append(item)
    return recent


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

                <div style="margin-top: 18px;">
                    <div style="display: flex; gap: 8px; margin-bottom: 12px;">
                        <button type="button" class="history-button" data-days="30" style="width: auto;">Last 30 days</button>
                        <button type="button" class="history-button" data-days="60" style="width: auto;">Last 60 days</button>
                        <button type="button" class="history-button" data-days="90" style="width: auto;">Last 90 days</button>
                    </div>
                    <div id="history-chat" style="background: #fff; border: 1px solid #ddd; border-radius: 8px; min-height: 180px; padding: 12px; display: flex; flex-direction: column; gap: 10px;">
                        <div style="color: #666;">No price history yet.</div>
                    </div>
                </div>
            </div>

            <script>
                const statusBox = document.getElementById('status-box');
                const metaBox = document.getElementById('meta-box');
                const historyChat = document.getElementById('history-chat');

                function getPriceTone(price, previousPrice) {
                    if (previousPrice === undefined || previousPrice === null) {
                        return { tone: 'neutral', label: 'Current price', color: '#2d3748' };
                    }
                    if (Number(price) < Number(previousPrice)) {
                        return { tone: 'drop', label: 'Price dropped', color: '#0f9d58' };
                    }
                    if (Number(price) > Number(previousPrice)) {
                        return { tone: 'rise', label: 'Price increased', color: '#d93025' };
                    }
                    return { tone: 'same', label: 'No change', color: '#5f6368' };
                }

                function renderHistory(historyList, days) {
                    historyChat.innerHTML = '';
                    if (!historyList || historyList.length === 0) {
                        historyChat.innerHTML = '<div style="color: #666;">No price history for the last ' + days + ' days.</div>';
                        return;
                    }

                    let previousPrice = null;
                    historyList.forEach(item => {
                        const d = new Date(item.checked_at.replace(' ', 'T'));
                        const price = Number(item.price);
                        const { label, color } = getPriceTone(price, previousPrice);
                        previousPrice = price;

                        const container = document.createElement('div');
                        container.style.display = 'flex';
                        container.style.justifyContent = 'flex-end';

                        const bubble = document.createElement('div');
                        bubble.style.maxWidth = '85%';
                        bubble.style.padding = '10px 14px';
                        bubble.style.borderRadius = '12px';
                        bubble.style.background = label === 'Price dropped' ? '#e6f8ee' : label === 'Price increased' ? '#fdecea' : '#f1f3f4';
                        bubble.style.border = '1px solid ' + (label === 'Price dropped' ? '#bfe8d0' : label === 'Price increased' ? '#f4c7c3' : '#e0e0e0');
                        bubble.style.color = color;
                        bubble.style.boxShadow = '0 1px 2px rgba(0,0,0,0.06)';

                        const mainLine = document.createElement('div');
                        mainLine.textContent = label + ': $' + item.price;
                        mainLine.style.fontWeight = '600';

                        const timeLine = document.createElement('div');
                        timeLine.textContent = d.toLocaleString();
                        timeLine.style.fontSize = '11px';
                        timeLine.style.textAlign = 'right';
                        timeLine.style.marginTop = '6px';
                        timeLine.style.opacity = '0.85';

                        bubble.appendChild(mainLine);
                        bubble.appendChild(timeLine);
                        container.appendChild(bubble);
                        historyChat.appendChild(container);
                    });
                }

                async function loadStatus() {
                    const response = await fetch('/status');
                    const data = await response.json();
                    const priceText = data.last_price !== null ? '$' + data.last_price : 'No price yet';
                    statusBox.textContent = data.status + ' | Current price: ' + priceText;
                    metaBox.textContent = data.url ? 'URL: ' + data.url + ' | Check interval: ' + data.interval + 's' : 'No active monitor';

                    const activeDays = document.querySelector('.history-button.active')?.dataset.days || '30';
                    const historyList = data.history_by_days && data.history_by_days[activeDays] ? data.history_by_days[activeDays] : [];
                    renderHistory(historyList, Number(activeDays));
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

                document.querySelectorAll('.history-button').forEach(button => {
                    button.addEventListener('click', () => {
                        document.querySelectorAll('.history-button').forEach(b => b.classList.remove('active'));
                        button.classList.add('active');
                        loadStatus();
                    });
                });

                document.querySelector('.history-button[data-days="30"]').classList.add('active');
                setInterval(loadStatus, 5000);
                loadStatus();
            </script>
        </body>
        </html>
        '''
    )


@app.get("/status")
def status():
    history = MONITOR_STATE.get("history", [])
    return jsonify({
        "url": MONITOR_STATE["url"],
        "interval": MONITOR_STATE["interval"],
        "running": MONITOR_STATE["running"],
        "status": MONITOR_STATE["status"],
        "last_price": str(MONITOR_STATE["last_price"]) if MONITOR_STATE["last_price"] is not None else None,
        "last_checked": MONITOR_STATE["last_checked"],
        "history_30_count": len(get_history_for_days(history, 30)),
        "history_60_count": len(get_history_for_days(history, 60)),
        "history_90_count": len(get_history_for_days(history, 90)),
        "history_by_days": {
            "30": get_history_for_days(history, 30),
            "60": get_history_for_days(history, 60),
            "90": get_history_for_days(history, 90),
        },
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
    MONITOR_STATE["history"] = load_history()

    thread = threading.Thread(target=run_monitor_loop, args=(url, MONITOR_STATE["interval"]), daemon=True)
    thread.start()
    return jsonify({"status": f"Monitoring started for {url} every {MONITOR_STATE['interval']} seconds."})


def run_monitor_loop(url: str, interval_seconds: int) -> None:
    last_price: Optional[Decimal] = None
    history = load_history()
    MONITOR_STATE["history"] = history

    while MONITOR_STATE["running"] and MONITOR_STATE["url"] == url:
        try:
            price = fetch_price(url)
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            MONITOR_STATE["last_checked"] = timestamp
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
                history.append({"checked_at": timestamp, "price": str(price)})
                history = history[-2000:]
                MONITOR_STATE["history"] = history
                save_history(history)
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
