import pandas as pd
import os

# ==========================================
# 1. パラメータ設定
# ==========================================
INPUT_DIR = "calculated_data"
# ★変更点：出力先をATR専用のフォルダに変更
RESULT_DIR = "simulation_results_atr"
SIM_MONTHS = 6

# --- 運用設定 ---
INITIAL_CAPITAL_RATE = 1.0      

# --- エントリー条件 (変更なし) ---
TREND_THRESHOLD = -0.01
GAP_DOWN_LIMIT = 0.99
PULLBACK_LIMIT = 0.98
ENTRY_MA_MID_UPPER = 1.01

# --- イグジット条件 (ATRベースの可変ルール) ---
ATR_MULTI_STOP = 1.5            # 初期損切(ハードストップ)：エントリー価格から【ATRの2.0倍】下落で発動
ATR_MULTI_TRAIL = 2.0           # トレーリングストップ：期間最高値から【ATRの2.5倍】下落で利益確定
PROFIT_TARGET_ATR_RATIO = 1.0   # トレイル発動トリガー：エントリー価格から【ATRの1.5倍】上昇したらトレイルモードON

# ==========================================
# 2. シミュレーションロジック
# ==========================================

def run_realistic_simulation_auto():
    os.makedirs(RESULT_DIR, exist_ok=True)
    summary_reports = []

    all_files = [f for f in os.listdir(INPUT_DIR) if f.endswith('_analyzed.csv')]
    
    if not all_files:
        print(f"× {INPUT_DIR} に解析済みデータが見つかりません。")
        return

    print(f"--- 複利運用シミュレーション (ATR可変ルール・累積率ベース) ---")
    
    for file_name in all_files:
        ticker = file_name.replace("_analyzed.csv", "")
        file_path = os.path.join(INPUT_DIR, file_name)
        
        df = pd.read_csv(file_path, index_col="Date", parse_dates=True)
        
        # 02でATRが計算されているかチェック（計算されていない場合の簡易フォールバック）
        if 'ATR' not in df.columns:
            high_low = df['High'] - df['Low']
            high_cp = (df['High'] - df['Close'].shift(1)).abs()
            low_cp = (df['Low'] - df['Close'].shift(1)).abs()
            tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
            df['ATR'] = tr.rolling(window=14).mean().round(1)

        latest_date = df.index.max()
        sim_start_date = latest_date - pd.DateOffset(months=SIM_MONTHS)
        
        try:
            start_idx = df.index.get_indexer([sim_start_date], method='bfill')[0]
        except:
            start_idx = 1
            
        if start_idx < 1: start_idx = 1

        # --- 変数初期化 ---
        current_capital = INITIAL_CAPITAL_RATE 
        position = 0
        buy_price = 0
        buy_atr = 0            
        max_close_since_buy = 0
        trailing_active = False 
        trade_history = []
        holding_days = 0 

        for i in range(start_idx, len(df)):
            is_latest_data = (i == len(df) - 1)
            
            c_close = df['Close'].iloc[i]    
            p_close = df['Close'].iloc[i-1]  
            p_low = df['Low'].iloc[i-1]      
            c_open = df['Open'].iloc[i]      
            c_atr = df['ATR'].iloc[i]        
            
            p_h, c_h = df['MACD_Hist'].iloc[i-1], df['MACD_Hist'].iloc[i]
            p_ma_s, c_ma_s = df['MA_Short'].iloc[i-1], df['MA_Short'].iloc[i]
            p_ma_m, c_ma_m = df['MA_Mid'].iloc[i-1], df['MA_Mid'].iloc[i]

            if not is_latest_data:
                next_date = df.index[i+1]
                next_open = df['Open'].iloc[i+1]
                next_low = df['Low'].iloc[i+1]   
            
            # --- 【エントリー判定】 ---
            if position == 0:
                ma_slope_rate = (c_ma_m - p_ma_m) / p_ma_m
                is_trend_acceptable = (ma_slope_rate >= TREND_THRESHOLD)
                
                cond1 = (p_h <= 0 and c_h > 0) 
                cond2 = (p_ma_s <= p_ma_m and c_ma_s > c_ma_m)
                
                is_not_gap_down = (c_open > p_low * GAP_DOWN_LIMIT)
                is_gentle_pullback = (c_close > p_close * PULLBACK_LIMIT)
                cond3_base = (p_close > p_ma_m and c_close < c_ma_m * ENTRY_MA_MID_UPPER) and (c_ma_s > c_ma_m)
                cond3 = cond3_base and is_not_gap_down and is_gentle_pullback

                entry_reason = ""
                if is_trend_acceptable:
                    if cond1: entry_reason = "MACD上抜け"
                    elif cond2: entry_reason = "ゴールデンクロス"
                    elif cond3: entry_reason = "押し目買い"

                if entry_reason:
                    if is_latest_data:
                        trade_history.append({
                            "Date": df.index[i].date(), "Action": "BUY_SIGNAL",
                            "Price": c_close, "Reason": entry_reason, "Profit": 0, "Capital": round(current_capital, 4)
                        })
                    else:
                        buy_price = next_open
                        buy_atr = df['ATR'].iloc[i+1] 
                        position = 1
                        max_close_since_buy = 0
                        trailing_active = False 
                        holding_days = 0 
                        trade_history.append({
                            "Date": next_date.date(), "Action": "BUY",
                            "Price": buy_price, "Reason": f"{entry_reason}", "Profit": 0, "Capital": round(current_capital, 4)
                        })

            # --- 【イグジット判定】 ---
            elif position == 1:
                holding_days += 1
                
                if is_latest_data:
                    trade_history.append({
                        "Date": df.index[i].date(), "Action": "HOLDING",
                        "Price": c_close, "Reason": "POS_OPEN", "Profit": 0, "Capital": round(current_capital, 4)
                    })
                else:
                    if c_close > max_close_since_buy:
                        max_close_since_buy = c_close
                    
                    if not trailing_active and (c_close >= buy_price + (buy_atr * PROFIT_TARGET_ATR_RATIO)):
                        trailing_active = True
                    
                    if holding_days <= 1 and not trailing_active:
                        continue
                    
                    sell_trigger = False
                    sell_reason = ""
                    sell_price = 0
                    
                    hard_stop_price = round(buy_price - (buy_atr * ATR_MULTI_STOP), 1)
                    stop_price = round(max_close_since_buy - (c_atr * ATR_MULTI_TRAIL), 1)
                    
                    if next_low <= hard_stop_price:
                        sell_trigger = True
                        sell_reason = "ハードストップ"
                        sell_price = next_open if next_open <= hard_stop_price else hard_stop_price
                    elif trailing_active and (next_low <= stop_price):
                        sell_trigger = True
                        sell_reason = "トレーリングストップ"
                        sell_price = next_open if next_open <= stop_price else stop_price

                    if sell_trigger:
                        profit_per_share = round(sell_price - buy_price, 2)
                        
                        trade_return_rate = sell_price / buy_price
                        current_capital *= trade_return_rate
                        
                        trade_history.append({
                            "Date": next_date.date(), "Action": "SELL",
                            "Price": sell_price, "Reason": sell_reason, "Profit": profit_per_share, "Capital": round(current_capital, 4)
                        })
                        position = 0
                        buy_price = 0
                        buy_atr = 0
                        max_close_since_buy = 0
                        trailing_active = False
                        holding_days = 0

        if not trade_history:
            continue

        result_df = pd.DataFrame(trade_history)
        result_df.to_csv(f"{RESULT_DIR}/{ticker}_trades.csv", index=False)
        
        profit_rate_pct = round((current_capital - 1.0) * 100, 2)
        trade_count = len(result_df[result_df['Action'] == 'SELL'])
        
        summary_reports.append({
            "Ticker": ticker,
            "Initial_Capital": INITIAL_CAPITAL_RATE,
            "Final_Capital": round(current_capital, 4),
            "Total_Profit_JPY": 0,
            "Profit_Rate_Pct": profit_rate_pct,
            "Trade_Count": trade_count
        })
        print(f"◎ {ticker}: 最終累積率 {current_capital:.4f} (利益率: {profit_rate_pct}%)")

    if summary_reports:
        summary_df = pd.DataFrame(summary_reports)
        summary_df.to_csv(f"{RESULT_DIR}/overall_summary.csv", index=False)
    print(f"\n--- ATR可変シミュレーション完了 ---")

if __name__ == "__main__":
    run_realistic_simulation_auto()