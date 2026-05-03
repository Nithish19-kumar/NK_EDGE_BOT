import os
import requests
import feedparser
import schedule
import time
import threading
from datetime import datetime
import pytz
import logging
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
IST = pytz.timezone("Asia/Kolkata")
analyzer = SentimentIntensityAnalyzer()

def get_sentiment(text):
    score = analyzer.polarity_scores(text)["compound"]
    if score >= 0.05:
        return "🟢 Positive", score
    elif score <= -0.05:
        return "🔴 Negative", score
    else:
        return "⚪ Neutral", score

def send_message(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        logger.info("Message sent to Telegram")
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")

NEWS_FEEDS = [
    {"name": "MoneyControl", "url": "https://www.moneycontrol.com/rss/latestnews.xml"},
    {"name": "Mint",         "url": "https://www.livemint.com/rss/markets"},
    {"name": "ET Markets",   "url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"},
    {"name": "Business Standard", "url": "https://www.business-standard.com/rss/markets-106.rss"},
]

sent_news_ids = set()

def fetch_market_news():
    logger.info("Fetching market news...")
    messages = []
    for feed_info in NEWS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:3]:
                entry_id = entry.get("id", entry.get("link", ""))
                if entry_id and entry_id not in sent_news_ids:
                    sent_news_ids.add(entry_id)
                    title = entry.get("title", "No title")
                    link  = entry.get("link", "")
                    sentiment_label, score = get_sentiment(title)
                    messages.append(
                        f"📰 <b>{feed_info['name']}</b>\n"
                        f"{title}\n"
                        f"{sentiment_label} (score: {score:.2f})\n"
                        f"<a href='{link}'>Read more</a>"
                    )
        except Exception as e:
            logger.error(f"News fetch error ({feed_info['name']}): {e}")
    if messages:
        combined = "\n\n".join(messages[:6])
        send_message(f"🗞 <b>Market News Update</b>\n\n{combined}")

def market_open_summary():
    logger.info("Sending market open summary...")
    try:
        nifty_url  = "https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI?interval=1m&range=1d"
        sensex_url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EBSESN?interval=1m&range=1d"
        headers = {"User-Agent": "Mozilla/5.0"}
        nr = requests.get(nifty_url,  headers=headers, timeout=10).json()
        sr = requests.get(sensex_url, headers=headers, timeout=10).json()
        nifty_price  = nr["chart"]["result"][0]["meta"]["regularMarketPrice"]
        nifty_prev   = nr["chart"]["result"][0]["meta"]["chartPreviousClose"]
        sensex_price = sr["chart"]["result"][0]["meta"]["regularMarketPrice"]
        sensex_prev  = sr["chart"]["result"][0]["meta"]["chartPreviousClose"]
        nifty_chg  = nifty_price  - nifty_prev
        sensex_chg = sensex_price - sensex_prev
        nifty_pct  = (nifty_chg  / nifty_prev)  * 100
        sensex_pct = (sensex_chg / sensex_prev) * 100
        nifty_arrow  = "🟢" if nifty_chg  >= 0 else "🔴"
        sensex_arrow = "🟢" if sensex_chg >= 0 else "🔴"
        if nifty_chg > 100:
            market_status = "<b>GAP UP</b> 📈"
        elif nifty_chg < -100:
            market_status = "<b>GAP DOWN</b> 📉"
        else:
            market_status = "<b>FLAT</b> ➡️"
        msg = (
            f"🔔 <b>Market Open — {datetime.now(IST).strftime('%d %b %Y, %I:%M %p')}</b>\n\n"
            f"{nifty_arrow} <b>Nifty 50:</b>  {nifty_price:,.2f}  ({nifty_chg:+.2f} | {nifty_pct:+.2f}%)\n"
            f"{sensex_arrow} <b>Sensex:</b>   {sensex_price:,.2f}  ({sensex_chg:+.2f} | {sensex_pct:+.2f}%)\n\n"
            f"Market is {market_status}"
        )
        send_message(msg)
    except Exception as e:
        logger.error(f"Market open summary error: {e}")
        send_message("⚠️ Market open summary failed. Check logs.")

NIFTY500_SYMBOLS = [
    "RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","ICICIBANK.NS",
    "HINDUNILVR.NS","SBIN.NS","BHARTIARTL.NS","ITC.NS","KOTAKBANK.NS",
    "LT.NS","AXISBANK.NS","ASIANPAINT.NS","MARUTI.NS","BAJFINANCE.NS",
    "TITAN.NS","SUNPHARMA.NS","WIPRO.NS","ULTRACEMCO.NS","NTPC.NS",
    "POWERGRID.NS","ONGC.NS","TATAMOTORS.NS","TATASTEEL.NS","ADANIENT.NS",
    "ADANIPORTS.NS","BAJAJFINSV.NS","DIVISLAB.NS","DRREDDY.NS","EICHERMOT.NS",
    "GRASIM.NS","HCLTECH.NS","HEROMOTOCO.NS","HINDALCO.NS","INDUSINDBK.NS",
    "JSWSTEEL.NS","M&M.NS","NESTLEIND.NS","TECHM.NS","TATACONSUM.NS",
    "CIPLA.NS","COALINDIA.NS","BPCL.NS","BRITANNIA.NS","SBILIFE.NS",
    "HDFCLIFE.NS","APOLLOHOSP.NS","UPL.NS","SHREECEM.NS","VEDL.NS"
]

alerted_stocks = {}

def check_stock_movers():
    logger.info("Checking Nifty 500 stock movers...")
    alerts = []
    headers = {"User-Agent": "Mozilla/5.0"}
    for symbol in NIFTY500_SYMBOLS:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
            r = requests.get(url, headers=headers, timeout=8).json()
            meta = r["chart"]["result"][0]["meta"]
            price     = meta["regularMarketPrice"]
            prev      = meta["chartPreviousClose"]
            volume    = meta.get("regularMarketVolume", 0)
            avg_vol   = meta.get("averageDailyVolume3Month", 1)
            change    = ((price - prev) / prev) * 100
            vol_ratio = volume / avg_vol if avg_vol > 0 else 0
            if abs(change) >= 2.0 and vol_ratio >= 1.2:
                last_alert = alerted_stocks.get(symbol, 0)
                now_ts = time.time()
                if now_ts - last_alert > 3600:
                    alerted_stocks[symbol] = now_ts
                    arrow = "🚀" if change > 0 else "💥"
                    name  = symbol.replace(".NS", "")
                    alerts.append(
                        f"{arrow} <b>{name}</b>: {price:.2f} ({change:+.2f}%)  "
                        f"Vol: {volume:,} ({vol_ratio:.1f}x avg)"
                    )
        except Exception as e:
            logger.debug(f"Stock check error {symbol}: {e}")
    if alerts:
        msg = "📊 <b>Stock Movers Alert (±2% + High Volume)</b>\n\n" + "\n".join(alerts[:15])
        send_message(msg)

nifty_low_alerted   = False
reversal_alerted    = False
prev_nifty_readings = []

def check_nifty_reversal():
    global nifty_low_alerted, reversal_alerted, prev_nifty_readings
    logger.info("Checking Nifty for reversal/drop...")
    try:
        url     = "https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI?interval=5m&range=1d"
        headers = {"User-Agent": "Mozilla/5.0"}
        r       = requests.get(url, headers=headers, timeout=10).json()
        result  = r["chart"]["result"][0]
        meta    = result["meta"]
        price      = meta["regularMarketPrice"]
        prev_close = meta["chartPreviousClose"]
        change_pts = price - prev_close
        prev_nifty_readings.append(price)
        if len(prev_nifty_readings) > 6:
            prev_nifty_readings.pop(0)
        if change_pts <= -250 and not nifty_low_alerted:
            nifty_low_alerted = True
            send_message(
                f"🚨 <b>NIFTY MAJOR DROP ALERT</b>\n\n"
                f"Nifty at <b>{price:,.2f}</b>\n"
                f"Down <b>{change_pts:+.2f} points</b> from prev close\n"
                f"⚠️ Monitor closely — possible panic selling"
            )
        if change_pts > -150:
            nifty_low_alerted = False
        if len(prev_nifty_readings) == 6:
            low_phase  = prev_nifty_readings[:3]
            rise_phase = prev_nifty_readings[3:]
            is_falling = all(low_phase[i] >= low_phase[i+1] for i in range(2))
            is_rising  = rise_phase[-1] > rise_phase[0]
            rise_amt   = rise_phase[-1] - min(low_phase)
            if is_falling and is_rising and rise_amt >= 40 and not reversal_alerted:
                reversal_alerted = True
                send_message(
                    f"🔄 <b>POSSIBLE NIFTY REVERSAL DETECTED</b>\n\n"
                    f"Nifty: <b>{price:,.2f}</b> ({change_pts:+.2f} pts)\n"
                    f"Bounced ~{rise_amt:.0f} pts from recent low\n"
                    f"📈 Watch for confirmation — potential recovery in progress"
                )
            elif not (is_falling and is_rising):
                reversal_alerted = False
    except Exception as e:
        logger.error(f"Nifty reversal check error: {e}")

from http.server import HTTPServer, BaseHTTPRequestHandler

class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")
    def log_message(self, format, *args):
        pass

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), PingHandler)
    logger.info(f"Web server running on port {port}")
    server.serve_forever()

def is_market_hours():
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    return (now.hour == 9 and now.minute >= 15) or \
           (10 <= now.hour <= 14) or \
           (now.hour == 15 and now.minute <= 30)

def setup_schedule():
    schedule.every(30).minutes.do(fetch_market_news)
    schedule.every().day.at("09:08").do(market_open_summary)
    schedule.every(15).minutes.do(lambda: check_stock_movers() if is_market_hours() else None)
    schedule.every(5).minutes.do(lambda: check_nifty_reversal() if is_market_hours() else None)
    logger.info("Scheduler set up successfully")

def run_scheduler():
    setup_schedule()
    send_message("🤖 <b>Stock Alert Bot Started!</b>\nMonitoring markets with Sentiment Analysis... 📊")
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    run_scheduler()
