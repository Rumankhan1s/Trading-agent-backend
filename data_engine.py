import yfinance as yf
import pandas as pd
from pymongo import MongoClient
import certifi

# Database Connection
MONGO_URI = "mongodb+srv://ruman:rumankhan123@preload.krqiopc.mongodb.net/?appName=Preload"

client = MongoClient(
    MONGO_URI,
    tlsCAFile=certifi.where(),
    tlsAllowInvalidCertificates=True
)

db = client["trading_db"]
collection = db["HistoricalData"]

def fetch_and_store_data(symbol, start_date):
    print(f"[SYSTEM] Fetching data for {symbol} from {start_date}...")
    
    stock = yf.Ticker(symbol)
    df = stock.history(start=start_date)
    
    if df.empty:
        print(f"❌ No data found for {symbol}")
        return

    df.dropna(inplace=True)
    df.reset_index(inplace=True)
    df['Date'] = df['Date'].astype(str)
    
    data_dict = df.to_dict("records")
    
    for record in data_dict:
        record['Symbol'] = symbol

    collection.delete_many({"Symbol": symbol})
    collection.insert_many(data_dict)
    
    print(f"✅ BINGO! Successfully stored {len(data_dict)} days of data for {symbol} in MongoDB.")

if __name__ == "__main__":
    # 🧠 The Pro-Level Fix: Har stock ki apni valid start date
    watchlist = {
        "RELIANCE.NS": "2015-01-01",
        "ZOMATO.NS": "2022-01-01",   # Zomato ko sirf uske IPO ke baad se uthayenge!
        "^NSEI": "2015-01-01",
        "^BSESN": "2015-01-01",
        "HDFCBANK.NS": "2015-01-01"
    }
    
    # Ab loop dono cheezein (stock aur uski date) ek sath bheja karega
    for stock, safe_date in watchlist.items():
        fetch_and_store_data(stock, start_date=safe_date)






       