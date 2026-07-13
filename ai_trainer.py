import pandas as pd
from pymongo import MongoClient
import certifi
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import ta  # Technical Analysis Library
import data_engine

# 1. Database Connection (Jo humne set kiya tha)
MONGO_URI = "mongodb+srv://ruman:rumankhan123@preload.krqiopc.mongodb.net/?appName=Preload"
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where(), tlsAllowInvalidCertificates=True)
db = client["trading_db"]
collection = db["HistoricalData"]

def train_ai_model(symbol):
    print(f"[SYSTEM] Waking up AI to analyze {symbol}...")
    
    # Database check
    data = list(collection.find({"Symbol": symbol}))
    
    # 🔥 NAYA AUTO-FETCH LOGIC 🔥
    if not data:
        print(f"⚠️ [SYSTEM] Data for {symbol} not in DB. Auto-fetching now...")
        try:
            # Pura data live download karke DB mein save kar denge
            data_engine.fetch_and_store_data(symbol, start_date="2015-01-01")
            # Save hone ke baad wapas DB se uthayenge
            data = list(collection.find({"Symbol": symbol}))
            
            if not data:
                return {"status": "error", "message": f"Stock {symbol} exists hi nahi karta ya Yahoo par nahi hai."}
        except Exception as e:
            return {"status": "error", "message": f"Live fetch failed: {str(e)}"}
            
    df = pd.DataFrame(data)
    
    # 2. FEATURE ENGINEERING (AI ki Aankhein)
    print("[SYSTEM] Calculating Advanced Technical Indicators...")
    df = df.sort_values('Date') 
    
    # Purane Indicators
    df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
    df['SMA_50'] = ta.trend.SMAIndicator(df['Close'], window=50).sma_indicator()
    df['SMA_200'] = ta.trend.SMAIndicator(df['Close'], window=200).sma_indicator()
    
    # 🔥 NAYE INDICATORS (The Upgrade)
    # MACD (Momentum batayega)
    df['MACD'] = ta.trend.MACD(df['Close']).macd()
    
    # Bollinger Bands (Market ki Volatility/Risk batayega)
    indicator_bb = ta.volatility.BollingerBands(close=df["Close"], window=20, window_dev=2)
    df['BB_High'] = indicator_bb.bollinger_hband()
    df['BB_Low'] = indicator_bb.bollinger_lband()
    
    df.dropna(inplace=True)
    # 3. THE TARGET (Bot ko kya sikhana hai?)
    # Logic: Agar "Kal" ka closing price "Aaj" se zyada hai, toh = 1 (BUY), warna = 0 (SELL)
    df['Target'] = (df['Close'].shift(-1) > df['Close']).astype(int)
    df.dropna(inplace=True)
    
    # 4. MACHINE LEARNING TRAINING
    print("[SYSTEM] Training Random Forest Brain...")
    
    # Ye saari details AI check karega decision lene se pehle
   # Naye features list mein add kar diye
    features = ['Open', 'High', 'Low', 'Close', 'Volume', 'RSI', 'SMA_50', 'SMA_200', 'MACD', 'BB_High', 'BB_Low']
    X = df[features]
    y = df['Target']
    
    # Data Split: 80% data par AI padhai karega, aur 20% par hum uska Exam lenge
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
    
    # The Core Algorithm
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
   # Exam Time (Testing on Unseen Data)
    predictions = model.predict(X_test)
    accuracy = accuracy_score(y_test, predictions) * 100
    
    # ---------------------------------------------------------
    # 🔥 THE REAL AI PREDICTION (OPTION A) 🔥
    # ---------------------------------------------------------
    # Database ke aakhri (latest) din ka data uthao
    latest_features = X.tail(1) 
    
    # Apna AI model us aakhri din ke data par apna dimaag lagayega
    live_prediction = model.predict(latest_features)[0]
    
    # Humara data engine 1 ko 'BUY' aur 0 ko 'SELL/HOLD' manta hai
    real_signal = "BUY" if live_prediction == 1 else "SELL"
    
    print(f"[AI ENGINE] Real Live Prediction Generated: {real_signal}")
    
    return {
        "status": "success",
        "symbol": symbol,
        "accuracy": round(accuracy, 2),
        "signal": real_signal # Yahan humne hardcoded "BUY" hata diya!
    }


if __name__ == "__main__":
    # Test ke liye Reliance ka data AI ko bhej rahe hain
    train_ai_model("RELIANCE.NS")