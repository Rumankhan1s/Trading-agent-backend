import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import RandomizedSearchCV

print("Step 1: Downloading Market Data...")
ticker = "RELIANCE.NS" 
data = yf.download(ticker, start="2020-01-01", end="2025-01-01")

print("Step 2: Advanced Feature Engineering (Adding RSI & MACD)...")

# 1. Simple Moving Averages (Purane wale)
data['SMA_10'] = data['Close'].rolling(window=10).mean()
data['SMA_50'] = data['Close'].rolling(window=50).mean()

# 2. Calculating RSI (14-day)
delta = data['Close'].diff() # Aaj aur kal ke price ka difference
gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
rs = gain / loss
data['RSI_14'] = 100 - (100 / (1 + rs))

# 3. Calculating MACD
exp1 = data['Close'].ewm(span=12, adjust=False).mean() # 12-day Exponential Average
exp2 = data['Close'].ewm(span=26, adjust=False).mean() # 26-day Exponential Average
data['MACD'] = exp1 - exp2
data['Signal_Line'] = data['MACD'].ewm(span=9, adjust=False).mean()

# Jo rows shuruat mein khali reh gayi calculations ki wajah se, unhe hata do
data = data.dropna()

print("Step 3: Defining the Target...")
# TARGET: Agar agle din ka close price aaj se zyada hai, toh 1 (Buy), warna 0
data['Target'] = (data['Close'].shift(-1) > data['Close']).astype(int)
data = data.dropna()

print("Step 4: Splitting Data for the AI...")
# DHYAN DO: Ab humne AI ko RSI aur MACD bhi de diya hai seekhne ke liye!
features = ['Open', 'High', 'Low', 'Close', 'Volume', 'SMA_10', 'SMA_50', 'RSI_14', 'MACD', 'Signal_Line']
X = data[features]
y = data['Target']

# 80% Training, 20% Testing
train_size = int(len(data) * 0.8)
X_train, X_test = X.iloc[:train_size], X.iloc[train_size:]
y_train, y_test = y.iloc[:train_size], y.iloc[train_size:]

print("\nStep 5: Training the AI Model (with Hyperparameter Tuning)...")
# Ye wo settings hain jo AI test karega
param_dist = {
    'n_estimators': [100, 200, 300, 400], # Kitne alag-alag trees banayein
    'max_depth': [5, 10, 15, 20, None],   # Kitna deep data ko analyze kare
    'min_samples_split': [2, 5, 10],      # Patterns ko kab split kare
}

print("AI khud apne liye best settings dhundh raha hai... (Isme 1-2 minute lag sakte hain)")
rf_base = RandomForestClassifier(random_state=42)

# RandomizedSearch 15 alag-alag combinations test karega
random_search = RandomizedSearchCV(estimator=rf_base, param_distributions=param_dist, 
                                   n_iter=15, cv=3, random_state=42, n_jobs=-1)

random_search.fit(X_train, y_train)

# AI ne jo sabse best version dhundha, hum usey apna main 'model' bana lenge
model = random_search.best_estimator_
print(f"Right Best Settings Found: {random_search.best_params_}")

print("\nStep 6: Testing the Model with High Confidence Threshold...")
# AI se har din ki probability (surety) puchte hain
probabilities = model.predict_proba(X_test)[:, 1] 

# THRESHOLD: AI jab 58% se zyada sure hoga, tabhi trade lega
CONFIDENCE_THRESHOLD = 0.58 
predictions = (probabilities > CONFIDENCE_THRESHOLD).astype(int)

accuracy = accuracy_score(y_test, predictions)
print(f"Upgraded AI Model Accuracy (with strict threshold): {accuracy * 100:.2f}%")

print("\n--- Step 7: Advanced Backtesting with Risk Management (Stop-Loss & Take-Profit) ---")
test_data = data.iloc[train_size:].copy()
test_data['Prediction'] = predictions
test_data['Daily_Return'] = test_data['Close'].pct_change()

# Raw returns if we just followed the AI blindly
test_data['Raw_Strategy_Return'] = test_data['Prediction'].shift(1) * test_data['Daily_Return']

# --- THE DEFENSE SYSTEM ---
STOP_LOSS = -0.015  # Agar 1.5% loss hua toh trade kaat do
TAKE_PROFIT = 0.02  # Agar 2.0% profit hua toh paisa jeb mein daal lo

def apply_risk_management(return_val):
    if pd.isna(return_val) or return_val == 0:
        return 0
    elif return_val <= STOP_LOSS:
        return STOP_LOSS # Bada loss hone se pehle exit
    elif return_val >= TAKE_PROFIT:
        return TAKE_PROFIT # Profit book kar liya
    else:
        return return_val # Normal return

# Apply our defense system to the AI's trades
test_data['Managed_Strategy_Return'] = test_data['Raw_Strategy_Return'].apply(apply_risk_management)

capital = 100000  

# Dono scenarios calculate kar rahe hain (With and Without Risk Management)
test_data['Cumulative_Market'] = (1 + test_data['Daily_Return']).cumprod() * capital
test_data['Cumulative_Raw_Strategy'] = (1 + test_data['Raw_Strategy_Return']).cumprod() * capital
test_data['Cumulative_Managed_Strategy'] = (1 + test_data['Managed_Strategy_Return']).cumprod() * capital

final_market_value = test_data['Cumulative_Market'].iloc[-1]
final_raw_value = test_data['Cumulative_Raw_Strategy'].iloc[-1]
final_managed_value = test_data['Cumulative_Managed_Strategy'].iloc[-1]

print(f"Starting Capital: Rs. {capital}")
print(f"Final Capital (Market Baseline): Rs. {final_market_value:.2f}")
print(f"Final Capital (AI Without Stop-Loss): Rs. {final_raw_value:.2f}")
print(f"Final Capital (AI WITH Stop-Loss & Take-Profit): Rs. {final_managed_value:.2f}")

market_roi = ((final_market_value - capital) / capital) * 100
managed_roi = ((final_managed_value - capital) / capital) * 100

print(f"\nMarket ROI: {market_roi:.2f}%")
print(f"Smart AI Strategy ROI (with Risk Management): {managed_roi:.2f}%")

print("\n--- Step 8: Generating Performance Graph ---")
plt.figure(figsize=(12, 6))

# Market ki performance (Red Line)
plt.plot(test_data.index, test_data['Cumulative_Market'], label='Market (Buy & Hold)', color='red', alpha=0.7)

# AI ki performance (Green Line)
plt.plot(test_data.index, test_data['Cumulative_Managed_Strategy'], label='Smart AI Strategy', color='green', linewidth=2)

plt.title('AI Trading Bot vs Market Performance (Reliance)')
plt.xlabel('Date')
plt.ylabel('Portfolio Value (Rs.)')
plt.legend()
plt.grid(True)

print("Graph generate ho raha hai... (Ek nayi window open hogi)")
plt.show()