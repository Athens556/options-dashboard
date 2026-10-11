import pandas as pd
from datetime import datetime
import urllib.parse
import time

def fetch_google_news(symbol, limit=5):
    """
    Fetches news from Google News RSS feed for a given symbol.
    """
    try:
        # Construct query: Symbol + stock + India
        query = f"{symbol} stock India"
        encoded_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"
        
        import feedparser
        import requests
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        feed = feedparser.parse(response.content)
        
        articles = []
        for entry in feed.entries[:limit]:
            published = entry.get('published', '')
            try:
                # Try to parse date for better display
                # Format usually: 'Thu, 18 Dec 2025 07:00:00 GMT'
                dt = datetime.strptime(published.replace(' GMT', ''), '%a, %d %b %Y %H:%M:%S')
                published_str = dt.strftime('%Y-%m-%d %H:%M')
            except:
                published_str = published

            articles.append({
                'title': entry.title,
                'link': entry.link,
                'published': published_str,
                'source': entry.source.title if hasattr(entry, 'source') else 'Google News'
            })
            
        return articles
    except Exception as e:
        print(f"Error fetching news: {e}")
        return []

def fetch_google_trends(symbol, retries=3, backoff_factor=10):
    """
    Fetches Google Trends interest over time.
    Uses DB Caching to avoid Rate Limits.
    """
    try:
        from pytrends.request import TrendReq
        from modules.dashboard.db_manager import DBManager
        import random
        
        db = DBManager()
        
        # 1. Check Cache
        cached_data = db.get_trends_cache(symbol)
        if cached_data:
            df = pd.DataFrame(cached_data)
            if not df.empty:
                df.index = pd.to_datetime(df.index)
                return df
        
        # 2. Rate Limit Handling / random backoff
        time.sleep(random.uniform(1.0, 3.0)) 
        
        # API Call Logic
        attempt = 0
        while attempt <= retries:
            try:
                pytrends = TrendReq(hl='en-IN', tz=330, timeout=(10,25))
                kw_list = [symbol]
                pytrends.build_payload(kw_list, cat=0, timeframe='today 12-m', geo='IN', gprop='')
                df = pytrends.interest_over_time()
                
                if not df.empty:
                    df = df.drop(columns=['isPartial'], errors='ignore')
                    
                    # 3. Save to Cache
                    df_copy = df.copy()
                    df_copy.index = df_copy.index.strftime('%Y-%m-%d')
                    data_dict = df_copy.to_dict()
                    db.save_trends_cache(symbol, data_dict)
                    
                    return df
                return pd.DataFrame()
                
            except Exception as e:
                error_str = str(e)
                print(f"Error fetching trends (Attempt {attempt+1}): {error_str}")
                
                if "429" in error_str:
                    if attempt == retries: break
                    wait = backoff_factor * (2 ** attempt)
                    print(f"Rate limit. Waiting {wait}s...")
                    time.sleep(wait)
                    attempt += 1
                else:
                    break
                    
    except Exception as e:
        print(f"Google Trends Top Level Error: {e}")
        
    return pd.DataFrame()

if __name__ == "__main__":
    # Test
    print("Testing News...")
    news = fetch_google_news("RELIANCE")
    for n in news:
        print(f"- {n['title']} ({n['published']})")
        
    print("\nTesting Trends...")
    trends = fetch_google_trends("RELIANCE")
    print(trends.head())
