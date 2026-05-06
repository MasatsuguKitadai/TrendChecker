import pandas as pd
import os

# ==========================================
# 1. パラメータ設定 (ここを編集して調整)
# ==========================================
# --- ディレクトリ設定 ---
INPUT_DIR = "calculated_data"
RESULT_DIR = "simulation_results"

# --- シミュレーション期間 ---
SIM_MONTHS = 6

# --- エントリー条件 ---
TREND_THRESHOLD = -0.01       # MA25の傾き許容閾値 (-0.01 = -1%)
GAP_DOWN_LIMIT = 0.99         # ギャップダウン許容範囲 (前日安値の99%以上)
PULLBACK_LIMIT = 0.98         # 押し目許容範囲 (前日終値の98%以上)
ENTRY_MA_MID_UPPER = 1.01     # 押し目買いの株価上限 (MA_Midの101%以下)

# --- イグジット条件 ---
PROFIT_TARGET_TRAILING = 1.05 # トレーリングを開始する利益率
HARD_STOP_LOSS = 0.95         # 買値からの損切りライン (5%損切り)
TRAILING_STOP_LOSS = 0.95     # 最高値からの逆指値ライン (5%下落)

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

    print(f"--- トレードシミュレーション (対象: {len(all_files)}銘柄) ---")
    
    for file_name in all_files:
        ticker = file_name.replace("_analyzed.csv", "")
        file_path = os.path.join(INPUT_DIR, file_name)
        
        df = pd.read_csv(file_path, index_col="Date", parse_dates=True)
        
        latest_date = df.index.max()
        sim_start_date = latest_date - pd.DateOffset(months=SIM_MONTHS)
        
        start_idx = df.index.get_indexer([sim_start_date], method='bfill')[0]
        if start_idx < 1:
            start_idx = 1
            
        position = 0
        buy_price = 0
        max_close_since_buy = 0
        trailing_active = False 
        total_profit = 0
        trade_history = []
        holding_days = 0 

        for i in range(start_idx, len(df)):
            is_latest_data = (i == len(df) - 1)
            
            c_close = df['Close'].iloc[i]    
            p_close = df['Close'].iloc[i-1]  
            p_low = df['Low'].iloc[i-1]      
            c_open = df['Open'].iloc[i]      
            
            p_h, c_h = df['MACD_Hist'].iloc[i-1], df['MACD_Hist'].iloc[i]
            p_ma_s, c_ma_s = df['MA_Short'].iloc[i-1], df['MA_Short'].iloc[i]
            p_ma_m, c_ma_m = df['MA_Mid'].iloc[i-1], df['MA_Mid'].iloc[i]

            if not is_latest_data:
                next_date = df.index[i+1]
                next_open = df['Open'].iloc[i+1]
                next_low = df['Low'].iloc[i+1]   
                is_sim_end_day = (i + 1 == len(df) - 1)
            
            # --- 【エントリー判定】 ---
            if position == 0:
                # MA25の傾き（前日比の騰落率）
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
                            "Price": c_close, "Reason": entry_reason, "Profit": 0
                        })
                    else:
                        position = 1
                        buy_price = next_open
                        max_close_since_buy = 0
                        trailing_active = False 
                        holding_days = 0 
                        trade_history.append({
                            "Date": next_date.date(), "Action": "BUY",
                            "Price": buy_price, "Reason": entry_reason, "Profit": 0
                        })

            # --- 【イグジット判定】 ---
            elif position == 1:
                holding_days += 1
                
                if is_latest_data:
                    trade_history.append({
                        "Date": df.index[i].date(), "Action": "HOLDING",
                        "Price": c_close, "Reason": "POS_OPEN", "Profit": 0
                    })
                else:
                    if holding_days <= 1:
                        continue

                    if c_close > max_close_since_buy:
                        max_close_since_buy = c_close
                    
                    if not trailing_active and (c_close >= buy_price * PROFIT_TARGET_TRAILING):
                        trailing_active = True
                    
                    sell_trigger = False
                    sell_reason = ""
                    sell_price = 0
                    
                    hard_stop_price = round(buy_price * HARD_STOP_LOSS, 1)
                    stop_price = round(max_close_since_buy * TRAILING_STOP_LOSS, 1)
                    
                    if next_low <= hard_stop_price:
                        sell_trigger = True
                        sell_reason = "HARD_STOP"
                        sell_price = next_open if next_open <= hard_stop_price else hard_stop_price
                    elif trailing_active and (next_low <= stop_price):
                        sell_trigger = True
                        sell_reason = f"TRAILING_STOP({stop_price})"
                        sell_price = next_open if next_open <= stop_price else stop_price
                    elif is_sim_end_day:
                        sell_trigger = True
                        sell_reason = "FINAL_SELL"
                        sell_price = df['Close'].iloc[i+1]

                    if sell_trigger:
                        profit = round(sell_price - buy_price, 1)
                        total_profit += profit
                        trade_history.append({
                            "Date": next_date.date(), "Action": "SELL",
                            "Price": sell_price, "Reason": sell_reason, "Profit": profit
                        })
                        position = 0
                        buy_price = 0
                        max_close_since_buy = 0
                        trailing_active = False
                        holding_days = 0

        result_df = pd.DataFrame(trade_history, columns=["Date", "Action", "Price", "Reason", "Profit"])
        result_df.to_csv(f"{RESULT_DIR}/{ticker}_trades.csv", index=False)
        
        total_profit = round(total_profit, 1)
        trade_count = len(result_df[result_df['Action'].isin(['BUY', 'SELL'])]) // 2
        
        summary_reports.append({
            "Ticker": ticker,
            "Total_Profit": total_profit,
            "Trade_Count": trade_count
        })
        print(f"◎ {ticker}: 完了 (損益 {total_profit:,.1f}円)")

    summary_df = pd.DataFrame(summary_reports)
    summary_df.to_csv(f"{RESULT_DIR}/overall_summary.csv", index=False)
    print(f"\n--- シミュレーション完了 ---")

if __name__ == "__main__":
    run_realistic_simulation_auto()