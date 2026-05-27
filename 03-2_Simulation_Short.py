# fileName: 03_Simulation_Short.py
import pandas as pd
import os

# ==========================================
# 1. パラメータ設定 (ショート・デイトレ版)
# ==========================================
INPUT_DIR = "calculated_data"
RESULT_DIR = "simulation_results_short"  
SIM_MONTHS = 6

# --- 運用設定 ---
INITIAL_CAPITAL_RATE = 1.0      # 初期値 1.0 = 100%

# --- エントリー条件 (デッドクロスのみ) ---
TREND_THRESHOLD = 0.01         

# --- イグジット条件 (デイトレ化のため不使用。05_Summary.pyとの同期互換性のために残置) ---
PROFIT_TARGET_TRAILING = 0.95  
HARD_STOP_LOSS = 1.05          
TRAILING_STOP_LOSS = 1.05      

# ==========================================
# 2. シミュレーションロジック
# ==========================================

def run_realistic_simulation_short_auto():
    os.makedirs(RESULT_DIR, exist_ok=True)
    summary_reports = []

    all_files = [f for f in os.listdir(INPUT_DIR) if f.endswith('_analyzed.csv')]
    
    if not all_files:
        print(f"× {INPUT_DIR} に解析済みデータが見つかりません。")
        return

    print(f"--- 複利運用シミュレーション (ショート・当日寄成 / 当日引成・デッドクロス限定版) ---")
    
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
        trade_history = []

        for i in range(start_idx, len(df)):
            is_latest_data = (i == len(df) - 1)
            
            c_close = df['Close'].iloc[i]    
            c_open = df['Open'].iloc[i]      
            
            p_ma_s, c_ma_s = df['MA_Short'].iloc[i-1], df['MA_Short'].iloc[i]
            p_ma_m, c_ma_m = df['MA_Mid'].iloc[i-1], df['MA_Mid'].iloc[i]

            # --- 【エントリー判定】 ---
            ma_slope_rate = (c_ma_m - p_ma_m) / p_ma_m
            is_trend_acceptable = (ma_slope_rate <= TREND_THRESHOLD)
            
            # デッドクロス判定 (MA5がMA25を上から下へ突き抜ける)
            cond_dc = (p_ma_s >= p_ma_m and c_ma_s < c_ma_m) 

            entry_reason = ""
            if is_trend_acceptable and cond_dc:
                entry_reason = "デッドクロス"

            # --- 【トレード処理 (デイトレ仕様)】 ---
            if entry_reason:
                if is_latest_data:
                    # 本日のデータでシグナル検出
                    trade_history.append({
                        "Date": df.index[i].date(), "Action": "SHORT_SIGNAL",
                        "Price": c_close, "Reason": entry_reason, "Profit": 0, "Capital": round(current_capital, 4)
                    })
                else:
                    # 翌営業日の「前場寄付き(Open)」で新規売、「後場引け(Close)」で即決済
                    next_date = df.index[i+1]
                    next_open = df['Open'].iloc[i+1]   
                    next_close = df['Close'].iloc[i+1] 
                    
                    # 1. 新規売りの記録
                    trade_history.append({
                        "Date": next_date.date(), "Action": "SHORT_SELL",
                        "Price": next_open, "Reason": entry_reason, "Profit": 0, "Capital": round(current_capital, 4)
                    })
                    
                    # 損益計算
                    profit_per_share = round(next_open - next_close, 2)
                    trade_return_rate = 1.0 + (next_open - next_close) / next_open
                    current_capital *= trade_return_rate
                    
                    # 2. 当日引け決済（買戻し）の記録
                    trade_history.append({
                        "Date": next_date.date(), "Action": "BUY_BACK",
                        "Price": next_close, "Reason": "当日引け決済", "Profit": profit_per_share, "Capital": round(current_capital, 4)
                    })

        result_df = pd.DataFrame(trade_history)
        result_df.to_csv(f"{RESULT_DIR}/{ticker}_trades.csv", index=False)
        
        profit_rate_pct = round((current_capital - 1.0) * 100, 2)
        trade_count = len(result_df[result_df['Action'] == 'BUY_BACK'])
        
        summary_reports.append({
            "Ticker": ticker,
            "Initial_Capital": INITIAL_CAPITAL_RATE,
            "Final_Capital": round(current_capital, 4),
            "Total_Profit_JPY": 0,
            "Profit_Rate_Pct": profit_rate_pct,
            "Trade_Count": trade_count
        })
        print(f"◎ {ticker}: 最終累積率 {current_capital:.4f} (利益率: {profit_rate_pct}%)")

    summary_df = pd.DataFrame(summary_reports)
    summary_df.to_csv(f"{RESULT_DIR}/overall_summary.csv", index=False)
    print(f"\n--- ショート・デイトレ版シミュレーション完了 ---")

if __name__ == "__main__":
    run_realistic_simulation_short_auto()