import pandas as pd
import os

# ==========================================
# 1. パラメータ設定
# ==========================================
INPUT_DIR = "calculated_data"
# ★変更点：出力先を固定5%専用のフォルダに変更
RESULT_DIR = "simulation_results_fixed"
SIM_MONTHS = 6

# --- 運用設定 ---
INITIAL_CAPITAL_RATE = 1.0      

# --- エントリー条件 ---
TREND_THRESHOLD = -0.01
GAP_DOWN_LIMIT = 0.99
PULLBACK_LIMIT = 0.98
ENTRY_MA_MID_UPPER = 1.01

# --- ★追加点：急騰（高値掴み）防止パラメータ ---
MAX_DAILY_RETURN = 1.04        # 当日の終値が前日終値の【4%】以上跳ね上がっていたら見逃す

# --- イグジット条件 ---
PROFIT_TARGET_TRAILING = 1.05  # 買値から5%上がったらトレイル発動
HARD_STOP_LOSS = 0.95          # 買値から5%下がったら初期損切
TRAILING_STOP_LOSS = 0.95      # 期間最高値から5%下がったら利益確定

# --- モメンタム利確設定 (ルール3) ---
USE_MOMENTUM_EXIT = True       # MACDデッドクロスによるモメンタム利確を有効にするか (True / False)

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

    print(f"--- 複利運用シミュレーション (固定5%ルール・急騰スルー機能搭載版) ---")
    
    for file_name in all_files:
        ticker = file_name.replace("_analyzed.csv", "")
        file_path = os.path.join(INPUT_DIR, file_name)
        
        df = pd.read_csv(file_path, index_col="Date", parse_dates=True)
        
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
                
                # ★追加：急騰判定（当日の終値が前日終値に対して跳ね上がりすぎていないか）
                is_not_spiking = (c_close < p_close * MAX_DAILY_RETURN)
                
                cond1 = (p_h <= 0 and c_h > 0) 
                cond2 = (p_ma_s <= p_ma_m and c_ma_s > c_ma_m)
                
                is_not_gap_down = (c_open > p_low * GAP_DOWN_LIMIT)
                is_gentle_pullback = (c_close > p_close * PULLBACK_LIMIT)
                cond3_base = (p_close > p_ma_m and c_close < c_ma_m * ENTRY_MA_MID_UPPER) and (c_ma_s > c_ma_m)
                cond3 = cond3_base and is_not_gap_down and is_gentle_pullback

                entry_reason = ""
                # ★変更点：is_not_spiking（急騰していないこと）をエントリーの必須条件に追加
                if is_trend_acceptable and is_not_spiking:
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
                    
                    if not trailing_active and (c_close >= buy_price * PROFIT_TARGET_TRAILING):
                        trailing_active = True
                    
                    if holding_days <= 1 and not trailing_active:
                        continue
                    
                    sell_trigger = False
                    sell_reason = ""
                    sell_price = 0
                    
                    # モメンタム利確（含み益が+5%以上のプラス圏にいる間、MACDがデッドクロスしたら翌朝即時利確）
                    if USE_MOMENTUM_EXIT and trailing_active and (p_h >= 0 and c_h < 0):
                        sell_trigger = True
                        sell_reason = "モメンタム利確(MACDデッドクロス)"
                        sell_price = next_open
                    
                    # モメンタム利確に該当しなかった場合のみ、通常のストップロス判定を実行
                    if not sell_trigger:
                        hard_stop_price = round(buy_price * HARD_STOP_LOSS, 1)
                        stop_price = round(max_close_since_buy * TRAILING_STOP_LOSS, 1)
                        
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
                        max_close_since_buy = 0
                        trailing_active = False
                        holding_days = 0

        # トレード履歴がない場合はCSVを出力しない（スキップ）
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
    print(f"\n--- 固定5%シミュレーション完了 ---")

if __name__ == "__main__":
    run_realistic_simulation_auto()