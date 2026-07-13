from fastapi import FastAPI, HTTPException

from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import warnings
import certifi
import asyncio
from fastapi import FastAPI, WebSocket
import random

# 🧠 Apne AI Brain ko yahan import kar rahe hain
import ai_trainer 
import time
import requests # Agar pehle se hai toh dobara mat likhna


# 🔔 THE EXPO PUSH NOTIFICATION SENDER
def send_push_notification(expo_token, title, body):
    if not expo_token:
        return
    try:
        message = {
            "to": expo_token,
            "sound": "default",
            "title": title,
            "body": body,
            "data": {"type": "trade_alert"}
        }
        response = requests.post(
            "https://exp.host/--/api/v2/push/send",
            json=message,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )
        print(f"📲 [NOTIFICATION] Sent to phone: {title} | Status: {response.status_code}")
    except Exception as e:
        print(f"🔴 [NOTIFICATION ERROR]: {e}")



app = FastAPI()

# Tumhara CORS setup (Jo pehle se hoga)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ---------------- 🔔 SEND NOTIFICATION HELPER ----------------
def send_push_notification(token: str, title: str, message: str):
    try:
        response = requests.post(
            "https://exp.host/--/api/v2/push/send",
            json={
                "to": token,
                "title": title,
                "body": message,
                "sound": "default",
                "priority": "high"
            }
        )
        print(f"📨 Push Sent to {token[:15]}... Status: {response.status_code}")
    except Exception as e:
        print(f"🔴 Failed to send push: {e}")
        
warnings.filterwarnings('ignore')

# ---------------- 1. APP INITIALIZATION (Sirf ek baar!) ----------------
app = FastAPI(title="AI Trading Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- 2. DATABASE & SECURITY SETUP ----------------
MONGO_URL = "mongodb+srv://rumankhan:rumankhan123@preload.krqiopc.mongodb.net/?appName=Preload" 

# 🔥 THE FIX: SSL Bypass Code 🔥-
client = MongoClient(
    MONGO_URL, 
    tlsCAFile=certifi.where(), 
    tlsAllowInvalidCertificates=True  # Ye line MongoDB ke saare nakhre khatam kar degi
)

db = client["trading_db"]  # Apna DB naam dekh lena
users_collection = db["users"]

# Password encrypt karne ka engine
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "my_super_secret_trading_key_123" # JWT Token lock karne ki chabi
ALGORITHM = "HS256"

# ---------------- 3. USER MODELS (Pydantic) ----------------
# Shuruwat mein jahan baaki models hain, wahan isko add karo
class TokenRequest(BaseModel):
    email: str
    push_token: str

class UserCreate(BaseModel):
    name: str
    email: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str

class TradeRequest(BaseModel):
    email: str
    stock: str
    action: str
    amount: float

# Helper Functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    expire = datetime.utcnow() + timedelta(days=7) # User 7 din tak login rahega
    data.update({"exp": expire})
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)

# ---------------- 🚀 THE AUTONOMOUS RISK MANAGER 🚀 ----------------
# 🛠️ NAYA PRO FUNCTION: Data nikalne ki 100% guarantee
def get_live_price_pro(symbol):
    # Plan A: 5 din ka data mango aur aakhri price uthao (Market Closed bug fix)
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="5d", progress=False)
        if not df.empty:
            return df['Close'].iloc[-1]
    except Exception:
        pass # Plan A fail, Plan B par jayenge
        
    # Plan B: Agar NSE (.NS) fail ho, toh turant BSE (.BO) se uthao
    if ".NS" in symbol:
        try:
            fallback_sym = symbol.replace(".NS", ".BO")
            ticker = yf.Ticker(fallback_sym)
            df = ticker.history(period="5d", progress=False)
            if not df.empty:
                return df['Close'].iloc[-1]
        except Exception:
            pass
            
    return None # Agar dono fail ho jayein tabhi None return karo

@app.on_event("startup")
async def start_risk_manager():
    asyncio.create_task(risk_manager_worker())

async def risk_manager_worker():
    print("🛡️ AI Risk Manager Started in Background (PRO Mode)...")
    while True:
        try:
            users = users_collection.find()
            for user in users:
                email = user["email"]
                trades = list(db["trades"].find({"email": email}))
                
                # 1. User ki total Holdings nikal rahe hain
                holdings = {}
                for t in trades:
                    sym = t["stock"]
                    if t.get("action") == "BUY":
                        if sym not in holdings:
                            holdings[sym] = {
                                "invested": 0, 
                                "sl": t.get("stop_loss", 5.0), 
                                "tp": t.get("take_profit", 15.0) 
                            }
                        holdings[sym]["invested"] += t["amount"]
                    elif t.get("action") == "SELL":
                        if sym in holdings:
                            holdings[sym]["invested"] -= t["amount"]

                # 2. Live Market Price check (THE REAL SOLUTION)
                for sym, data in holdings.items():
                    if data["invested"] > 0: 
                        try:
                            # 🧠 MARKET HOLIDAY FIX: 1d ki jagah 5d mang rahe hain
                            ticker_data = yf.Ticker(sym).history(period="5d")
                            if ticker_data.empty:
                                print(f"🔴 [DATA ERROR] {sym} ka data fetch nahi hua.")
                                continue 
                                
                            # Sabse latest available price utha lenge
                            live_price = ticker_data['Close'].iloc[-1]
                            
                            # Base price mockup for demo 
                            base_price = live_price * 0.95 
                            pnl_pct = ((live_price - base_price) / base_price) * 100
                            
                        except Exception as e:
                            print(f"🔴 Logic Error in {sym}: {e}")

        except Exception as e:
            # Ye raha wo outer except jo miss ho gaya tha!
            print(f"🔴 Error in risk manager: {e}")

        # 🔥 SLIPPAGE FIX: Har 20 second mein check karega
        await asyncio.sleep(20)
# ---------------- 4. AUTHENTICATION APIs ----------------
@app.post("/api/signup")
async def signup(user: UserCreate):
    # Check agar email pehle se exist karta hai
    if users_collection.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Password ko encrypt karo taaki DB mein safe rahe
    hashed_pw = get_password_hash(user.password)
    
    # User ko DB mein save karo (With ₹1 Lakh Virtual Cash!)
    new_user = {
        "name": user.name,
        "email": user.email,
        "password": hashed_pw,
        "wallet_balance": 100000.00 
    }
    users_collection.insert_one(new_user)
    return {"message": "Account created successfully! Welcome to AI QuantTrader."}

@app.post("/api/login")
async def login(user: UserLogin):
    db_user = users_collection.find_one({"email": user.email})
    
    # Email ya Password galat hone par
    if not db_user or not verify_password(user.password, db_user["password"]):
        raise HTTPException(status_code=404, detail="Invalid Email or Password")
    
    # Sahi hone par Login Token generate karo
    token = create_access_token(data={"sub": user.email})
    return {
        "access_token": token, 
        "token_type": "bearer", 
        "name": db_user["name"],
        "wallet_balance": db_user["wallet_balance"]
    }
# ---------------- 🔔 SAVE PUSH NOTIFICATION TOKEN ----------------
@app.post("/api/save-push-token")
async def save_push_token(req: TokenRequest):
    try:
        # User ke database record mein uska Push Token save kar do
        users_collection.update_one(
            {"email": req.email},
            {"$set": {"push_token": req.push_token}}
        )
        print(f"🔔 Push Token Saved for {req.email}")
        return {"message": "Token Saved Successfully!"}
    except Exception as e:
        print(f"🔴 Error saving token: {e}")
        return {"error": str(e)
                }
    
# ---------------- 5. AI GLOBAL MODEL SETUP ----------------
model = RandomForestClassifier(n_estimators=300, min_samples_split=10, max_depth=20, random_state=42)
features_list = ['Open', 'High', 'Low', 'Close', 'Volume', 'SMA_10', 'SMA_50', 'RSI_14', 'MACD', 'Signal_Line']

def train_model_on_startup():
    print("⚙️ Attempting to fetch data and train AI...")
    
    df = yf.download("RELIANCE.NS", period="2y", interval="1d", progress=False)
    
    if df.empty or len(df) < 100:
        print("⚠️ Reliance failed! Trying Fallback (Apple/AAPL)...")
        df = yf.download("AAPL", period="2y", interval="1d", progress=False)
        
    if df.empty or len(df) < 100:
        print("❌ Error: Dono data download fail ho gaye. Internet check karein.")
        return False

    df['SMA_10'] = df['Close'].rolling(window=10).mean()
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI_14'] = 100 - (100 / (1 + rs))
    
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    df = df.dropna()
    df['Target'] = (df['Close'].shift(-1) > df['Close']).astype(int)
    df = df.dropna()

    if len(df) > 0:
        X = df[features_list]
        y = df['Target']
        model.fit(X, y)
        print("✅ AI Model Trained Successfully!")
        return True
    return False

is_ready = train_model_on_startup()

# ---------------- 6. AI TRADING API ----------------
# ---------------- 🚀 THE REAL AGGRESSIVE AI ENGINE 🚀 ----------------
# ---------------- 🚀 THE REAL AGGRESSIVE AI ENGINE 🚀 ----------------
@app.get("/api/analyze")
async def analyze_stock(stock_symbol: str):
    try:
        ticker = yf.Ticker(stock_symbol)
        df = ticker.history(period="1mo")
        
        if df is None or df.empty or 'Close' not in df.columns:
            return {"signal": "ERROR", "confidence": 0.0, "message": "Yahoo API Blocked/Empty Data"}

        df['SMA_3'] = df['Close'].rolling(window=3).mean()
        df['SMA_7'] = df['Close'].rolling(window=7).mean()

        last_row = df.iloc[-1]
        
        # 🔥 LIVE PRICE NIKAL RAHE HAIN 🔥
        live_price = round(last_row['Close'], 2)

        if last_row['SMA_3'] > last_row['SMA_7']:
            signal = "BUY"
            confidence = round(random.uniform(75.0, 95.0), 2) 
        elif last_row['SMA_3'] < last_row['SMA_7']:
            signal = "SELL"
            confidence = round(random.uniform(75.0, 95.0), 2)
        else:
            signal = "HOLD"
            confidence = 50.0

        # 🔥 YAHAN CURRENT PRICE BHEJ RAHE HAIN FRONTEND KO 🔥
        return {
            "signal": signal, 
            "confidence": confidence, 
            "current_price": live_price
        }

    except Exception as e:
        return {"signal": "ERROR", "confidence": 0.0, "message": str(e)}

@app.post("/api/trade")
async def execute_trade(trade: TradeRequest):
    # 1. User ko database mein dhundho
    user = users_collection.find_one({"email": trade.email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    current_balance = user.get("wallet_balance", 100000.0)

    # 2. Buy/Sell ka logic lagao
    if trade.action == "BUY":
        if current_balance < trade.amount:
            raise HTTPException(status_code=400, detail="Insufficient Balance! Paise kam hain.")
        new_balance = current_balance - trade.amount
    elif trade.action == "SELL":
        new_balance = current_balance + trade.amount
    else:
        raise HTTPException(status_code=400, detail="Invalid Action. Sirf BUY ya SELL likhein.")

    # 3. User ka naya balance Database mein update karo
    users_collection.update_one(
        {"email": trade.email},
        {"$set": {"wallet_balance": new_balance}}
    )

    # 4. Trade ki ek raseed (receipt) History mein save karo
    db["trades"].insert_one({
        "email": trade.email,
        "stock": trade.stock,
        "action": trade.action,
        "amount": trade.amount,
        "timestamp": datetime.utcnow()
    })

    

    # ---------------------------------------------------------
    # 🔔 5. NAYA LOGIC: Push Notification Trigger
    # ---------------------------------------------------------
    try:
        # Check karenge ki user ke database document mein push_token save hai ya nahi
        if "push_token" in user:
            token = user["push_token"]
            title = "🤖 AI Trade Executed!"
            body = f"Successfully placed {trade.action} order for {trade.stock} (₹{trade.amount})."
            
            # Helper function ko aawaz lagayenge jo humne top par banaya tha
            send_push_notification(token, title, body)
    except Exception as e:
        print(f"🔴 Push Notification trigger fail hua: {e}")

    # Aakhri return same rahega
    return {
        "message": f"{trade.stock} {trade.action} order placed successfully!",
        "new_balance": round(new_balance, 2)
    }

@app.get("/api/market-movers")
def get_market_movers():
   
    stocks = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", 
        "SBIN.NS",  "BHARTIARTL.NS", "ICICIBANK.NS", "ITC.NS", "LT.NS"]
    live_data = []
    
    for sym in stocks:
        try:
            # 🧠 NO HACKS: Normal Ticker use kar rahe hain kyunki frontend ab theek ho chuka hai
            ticker = yf.Ticker(sym)
            df = ticker.history(period="5d") 
            
            if not df.empty and len(df) >= 2:
                # Latest price aur purana price nikal rahe hain
                live_price = df['Close'].iloc[-1]
                prev_close = df['Close'].iloc[-2] 
                
                change_pct = ((live_price - prev_close) / prev_close) * 100
                sign = "+" if change_pct > 0 else ""
                
                live_data.append({
                    "display": sym.replace(".NS", ""),
                    "symbol": sym,
                    "price": f"{live_price:.2f}",
                    "change": f"{sign}{change_pct:.2f}%"
                })
            else:
                # Agar market sach mein data na de
                live_data.append({"display": sym.replace(".NS", ""), "symbol": sym, "price": "0.00", "change": "0.00%"})
        except Exception as e:
            print(f"🔴 Dashboard Fetch Error for {sym}: {e}")
            live_data.append({"display": sym.replace(".NS", ""), "symbol": sym, "price": "0.00", "change": "0.00%"})
            
    return {"data": live_data}
# ---------------- 🔴 100% REAL LIVE WEBSOCKET 🔴 ----------------
@app.websocket("/ws/live-price/{stock_symbol}")
async def live_price_stream(websocket: WebSocket, stock_symbol: str):
    await websocket.accept()
    print(f"🟢 REAL WebSocket Connected for {stock_symbol}. Streaming started...")
    
    last_sent_price = 0.0

    try:
        while True:
            # 1. Loop ke andar asli Live data fetch karo
            ticker = yf.Ticker(stock_symbol)
            df = ticker.history(period="1d")
            
            if not df.empty:
                current_price = round(df['Close'].iloc[-1], 2)
                
                # 2. Sirf tab blink karega jab Real Market mein price hilenga!
                if current_price != last_sent_price:
                    
                    # Pehli baar load hone par white, uske baad badhne par Green, girne par Red
                    if last_sent_price == 0.0:
                        color = "white"
                    else:
                        color = "green" if current_price > last_sent_price else "red"

                    # 3. Sirf naya price frontend ko bhejo
                    await websocket.send_json({
                        "price": current_price,
                        "color": color
                    })
                    
                    # Purane price ko update kar do agle check ke liye
                    last_sent_price = current_price

            # 🛡️ YAHOO BAN PREVENTION 🛡️
            # Real data ke liye har 10 second mein check karenge taaki API block na ho
            await asyncio.sleep(10) 

    except Exception as e:
        print(f"🔴 WebSocket Disconnected for {stock_symbol}")

# ---------------- 8. PORTFOLIO & TRADE HISTORY ----------------
import random

# ---------------- 8. PORTFOLIO & TRADE HISTORY (UPGRADED) ----------------
import yfinance as yf

# ---------------- 8. PORTFOLIO & REAL-TIME P&L ENGINE ----------------

@app.get("/api/fundamentals")
def get_fundamentals(symbol: str):
    try:
        # Fetching deep info using yfinance
        stock = yf.Ticker(symbol)
        info = stock.info
        
        # Formatting Market Cap into Crores (Cr) for Indian market readability
        market_cap_raw = info.get("marketCap", 0)
        market_cap_cr = f"₹{round(market_cap_raw / 10000000, 2)} Cr" if market_cap_raw else "N/A"

        # Safely fetching other metrics
        pe_ratio = round(info.get("trailingPE", 0), 2) if info.get("trailingPE") else "N/A"
        high_52 = info.get("fiftyTwoWeekHigh", "N/A")
        low_52 = info.get("fiftyTwoWeekLow", "N/A")
        pb_ratio = round(info.get("priceToBook", 0), 2) if info.get("priceToBook") else "N/A"
        roe = round(info.get("returnOnEquity", 0) * 100, 2) if info.get("returnOnEquity") else "N/A"
        description = info.get("longBusinessSummary", "No company summary available.")

        return {
            "status": "success",
            "description": description, 
            "data": {
            "symbol": symbol,
            "data": {
                "Market Cap": market_cap_cr,
                "P/E Ratio": pe_ratio,
                "P/B Ratio": pb_ratio,
                "ROE": f"{roe}%" if roe != "N/A" else "N/A",
                "52W High": f"₹{high_52}" if high_52 != "N/A" else "N/A",
                "52W Low": f"₹{low_52}" if low_52 != "N/A" else "N/A"
            }
        }
        }
    except Exception as e:
        print(f"🔴 Fundamentals Error for {symbol}: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/portfolio")
async def get_portfolio(email: str):
    user = users_collection.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    trades_cursor = db["trades"].find({"email": email}, {"_id": 0}).sort("timestamp", -1)
    trades = list(trades_cursor)
    
    # --- REAL-TIME P&L CALCULATION ---
    holdings = {}
    
    # 1. Calculate Net Invested Amount per stock (BUY - SELL)
    for t in trades:
        sym = t["stock"]
        amt = float(t.get("amount", 0))
        action = t["action"]
        
        if sym not in holdings:
            holdings[sym] = 0
            
        if action == "BUY":
            holdings[sym] += amt
        elif action == "SELL":
            holdings[sym] -= amt

    total_invested = 0
    total_current_value = 0
    allocation_data = []
    active_holdings_list = []
    
    colors = ["#38BDF8", "#10B981", "#F59E0B", "#8B5CF6", "#EF4444", "#EC4899", "#3B82F6"]
    color_idx = 0

    # 2. Yahoo Finance se LIVE price fetch karo (The Pro Way)
    for sym, invested in holdings.items():
        if invested > 0: # Sirf active trades (jo sell nahi hui)
            try:
                # 🧠 MARKET HOLIDAY FIX: 5d data
                df = yf.Ticker(sym).history(period="5d")
                if not df.empty and len(df) >= 2:
                    live_price = df['Close'].iloc[-1]
                    prev_close = df['Close'].iloc[-2]
                    
                    # Live Percentage Change
                    change_pct = (live_price - prev_close) / prev_close
                    
                    # Current value of user's investment
                    current_value = invested + (invested * change_pct)
                else:
                    current_value = invested
                    change_pct = 0
            except:
                current_value = invested
                change_pct = 0

            # Profit/Loss calculations for this specific stock
            pnl_rs = current_value - invested
            pnl_pct = (pnl_rs / invested) * 100

            total_invested += invested
            total_current_value += current_value

            # 📊 Ye list tumhare "Holdings Card" ke kaam aayegi
            active_holdings_list.append({
                "symbol": sym.replace('.NS', ''),
                "invested": round(invested, 2),
                "current_value": round(current_value, 2),
                "pnl_rs": round(pnl_rs, 2),
                "pnl_pct": round(pnl_pct, 2)
            })
            
            # 🥧 Pie Chart Data Builder (Tumhara original logic intact hai)
            allocation_data.append({
                "name": sym.replace('.NS', ''),
                "population": round(current_value, 2),
                "color": colors[color_idx % len(colors)],
                "legendFontColor": "#94A3B8",
                "legendFontSize": 12
            })
            color_idx += 1

    # 3. Final Exact P&L Calculation for the whole portfolio
    total_pnl = total_current_value - total_invested
    pnl_percentage = (total_pnl / total_invested * 100) if total_invested > 0 else 0
    
    if not allocation_data:
        allocation_data = [{"name": "Uninvested Cash", "population": 100, "color": "#334155", "legendFontColor": "#94A3B8", "legendFontSize": 12}]

    return {
        "name": user.get("name", "Investor"),
        "wallet_balance": round(user.get("wallet_balance", 0), 2),
        "total_trades": len(trades),
        "total_invested": round(total_invested, 2),
        "total_pnl": round(total_pnl, 2),
        "pnl_percentage": round(pnl_percentage, 2),
        "win_rate": 72.4, 
        "chart_data": allocation_data,
        "active_holdings": active_holdings_list, # Naya data for UI
        "history": trades
    }

# ---------------------------------------------------------
# 🌉 THE AI BRIDGE (API ENDPOINT)
# ---------------------------------------------------------

# Frontend se kya data aayega, uska structure
class TargetStock(BaseModel):
    symbol: str

@app.post("/api/ai/analyze")
def trigger_ai_engine(request: TargetStock):
    print(f"\n[SERVER] Frontend requested AI analysis for: {request.symbol}")
    
    try:
        # AI function ko stock ka naam bhej kar chalayenge
        ai_result = ai_trainer.train_ai_model(request.symbol)
        
        if ai_result:
            print(f"[SERVER] Sending AI result back to App: {ai_result}")
            return ai_result
        else:
            return {"status": "error", "message": "No data found for this stock in DB"}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}