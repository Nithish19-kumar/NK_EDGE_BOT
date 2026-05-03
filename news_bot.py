import schedule
import hashlib
import json
import feedparser
import requests
import time
import yfinance as yf
from datetime import datetime, timezone, timedelta
import os

SEEN_FILE = "seen.json"
TOKEN   = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
IST = timezone(timedelta(hours=5, minutes=30))

POSITIVE_WORDS = ['profit','gain','rise','surge','jump','high','up','growth',
    'rally','strong','beat','record','buy','upgrade','positive','boom','win','success','dividend']
NEGATIVE_WORDS = ['loss','fall','drop','crash','low','down','weak','decline',
    'sell','downgrade','negative','bust','fail','cut','risk','warning','concern','trouble','debt']

def get_sentiment(headline):
    h = headline.lower()
    pos = sum(1 for w in POSITIVE_WORDS if w in h)
    neg = sum(1 for w in NEGATIVE_WORDS if w in h)
    if pos > neg:   return "POSITIVE", "🟢"
    elif neg > pos: return "NEGATIVE", "🔴"
    else:           return "NEUTRAL",  "⚪"

RSS_FEEDS = [
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms",
    "https://www.moneycontrol.com/rss/business.xml",
    "https://www.moneycontrol.com/rss/marketreports.xml",
    "https://www.moneycontrol.com/rss/results.xml",
    "https://www.livemint.com/rss/markets",
    "https://www.livemint.com/rss/companies",
    "https://www.business-standard.com/rss/markets-106.rss",
    "https://www.zeebiz.com/rss/india.xml",
    "https://www.sebi.gov.in/sebi_data/rss/sebilatestNews.xml",
    "https://www.chittorgarh.com/rss/ipo_news.asp",
]

INDIAN_KEYWORDS = [
    'nifty','sensex','bse','nse','sebi','rbi','india','indian',
    'rupee','inr','crore','lakh','reliance','tcs','infosys',
    'hdfc','icici','sbi','bajaj','tata','adani','wipro','ipo',
    'q4','q3','results','dividend','bonus','buyback',
    'muhurat','dalal','budget','repo rate','fii','dii'
]

def load_seen():
    try:
        with open(SEEN_FILE, 'r') as f:
            return set(json.load(f))
    except:
        return set()

def save_seen(seen):
    with open(SEEN_FILE, 'w') as f:
        json.dump(list(seen), f)

def get_hash(text):
    return hashlib.md5(text.encode()).hexdigest()

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"})

def is_indian_news(headline):
    return any(kw in headline.lower() for kw in INDIAN_KEYWORDS)

def get_category(headline):
    h = headline.lower()
    if any(x in h for x in ['sebi','rbi','repo','regulation']): return "🏛️ REGULATORY"
    elif any(x in h for x in ['ipo','listing','allotment']): return "🚀 IPO ALERT"
    elif any(x in h for x in ['result','profit','revenue','q4','q3']): return "📊 RESULTS"
    elif any(x in h for x in ['dividend','bonus','buyback','split']): return "💰 CORP ACTION"
    elif any(x in h for x in ['nifty','sensex','market']): return "📈 MARKET"
    else: return "⚡ NEWS"

def format_message(headline, label, emoji):
    time_now = datetime.now(IST).strftime('%I:%M %p | %d %b %Y')
    return (f"{get_category(headline)}\n━━━━━━━━━━━━━━━━\n"
            f"📰 {headline}\n━━━━━━━━━━━━━━━━\n"
            f"{emoji} {label}\n🕐 {time_now}\n📡 NK Edge Bot")

def fetch_news():
    articles = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:5]:
                if is_indian_news(entry.title):
                    articles.append(entry.title)
        except:
            pass
    return articles

seen_headlines = load_seen()

def check_new_news():
    global seen_headlines
    print(f"[{datetime.now(IST).strftime('%H:%M:%S')}] Checking news...")
    new_count = 0
    for headline in fetch_news():
        h = get_hash(headline)
        if h not in seen_headlines:
            seen_headlines.add(h)
            label, emoji = get_sentiment(headline)
            msg = format_message(headline, label, emoji)
            send_telegram(msg)
            time.sleep(2)
            new_count += 1
    save_seen(seen_headlines)
    print(f"✅ Sent {new_count} new articles")

schedule.every(5).minutes.do(check_new_news)
print("🤖 NK Edge Bot Started!\n📰 Checking news every 5 mins\n")
check_new_news()

while True:
    schedule.run_pending()
    time.sleep(30)
