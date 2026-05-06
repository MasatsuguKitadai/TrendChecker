import pandas as pd
import os

# --- 設定 ---
INPUT_DIR = "calculated_data"
RESULT_DIR = "simulation_results_short"

def run_short_simulation_auto():
    os.makedirs(RESULT_DIR, exist_ok=True)
    summary_reports = []

    all_files = [f for f in os.listdir(INPUT_DIR) if f.endswith('_analyzed.csv')]
    
    if not all_files:
        print(f"× {INPUT_DIR} に解析済みデータが見つかりません。")
        return

    print(f"--- 信用売りシミュレーション (対象: {len(all_files)}銘柄 / 下降トレンド限定版) ---")
    
    for file_name in all_files:
        ticker = file_name.replace("_analyzed.csv", "")
        file_path = os.path.join(INPUT_DIR, file_name)
        
        # データの読み込み
        df = pd.read_csv(file_path, index_col="Date", parse_dates=True)
        
        # --- シミュレーション対象期間（直近6ヶ月）の算出 ---
        latest_date = df.index.max()
        sim_start_date = latest_date - pd.DateOffset(months=6)
        
        start_idx = df.index.get_indexer([sim_start_date], method='bfill')[0]
        if start_idx < 1:
            start_idx = 1
            
        position = 0
        sell_price = 0
        min_close_since_sell = 9999999
        trailing_active = False 
        total_profit = 0
        trade_history = []
        holding_days = 0  # 【追加】保有日数を管理する変数

        # ループ実行：最新のデータ（今日）まで判定
        for i in range(start_idx, len(df)):
            is_latest_data = (i == len(df) - 1)
            
            # --- Day T (判定日) のデータ ---
            c_high = df['High'].iloc[i]
            c_close = df['Close'].iloc[i]
            p_h, c_h = df['MACD_Hist'].iloc[i-1], df['MACD_Hist'].iloc[i]
            p_ma_s, c_ma_s = df['MA_Short'].iloc[i-1], df['MA_Short'].iloc[i]
            p_ma_m, c_ma_m = df['MA_Mid'].iloc[i-1], df['MA_Mid'].iloc[i]

            # --- Day T+1 (翌日の実行) のデータ取得（最終日でない場合のみ） ---
            if not is_latest_data:
                next_date = df.index[i+1]
                next_open = df['Open'].iloc[i+1]
                next_high = df['High'].iloc[i+1]
                is_sim_end_day = (i + 1 == len(df) - 1)
            
            # --- 【トレンド判定】（ロジック維持） ---
            is_ma5_down = (c_ma_s < p_ma_s)
            is_ma25_down = (c_ma_m < p_ma_m)
            is_perfect_order = (c_ma_s > c_ma_m)

            # --- 【エントリー判定：空売り】 ---[cite: 2]
            if position == 0:
                cond1 = (p_h >= 0 and c_h < 0) and is_ma25_down

                entry_reason = ""
                if cond1: entry_reason = "トレンド×MACD下抜け"

                if entry_reason:
                    if is_latest_data:
                        # 明日のアクション用フラグ[cite: 2]
                        trade_history.append({
                            "Date": df.index[i].date(), "Action": "SHORT_SIGNAL",
                            "Price": c_close, "Reason": entry_reason, "Profit": 0
                        })
                    else:
                        position = 1
                        sell_price = next_open
                        min_close_since_sell = 9999999
                        trailing_active = False 
                        holding_days = 0  # 【追加】新規売り時は0でリセット[cite: 2]
                        trade_history.append({
                            "Date": next_date.date(), "Action": "SHORT_SELL",
                            "Price": sell_price, "Reason": entry_reason, "Profit": 0
                        })

            # --- 【イグジット判定】 ---[cite: 2]
            elif position == 1:
                holding_days += 1  # 【追加】保有日数をカウントアップ[cite: 2]
                
                if is_latest_data:
                    # 保有中フラグ[cite: 2]
                    trade_history.append({
                        "Date": df.index[i].date(), "Action": "HOLDING",
                        "Price": c_close, "Reason": "POS_OPEN", "Profit": 0
                    })
                else:
                    # 【追加】エントリーした次の日（保有1日目）は判定をスキップ[cite: 2]
                    if holding_days <= 1:
                        continue

                    if c_close < min_close_since_sell:
                        min_close_since_sell = c_close
                    if not trailing_active and (c_close <= sell_price * 0.97):
                        trailing_active = True
                    
                    sell_trigger = False
                    sell_reason = ""
                    buyback_price = 0
                    
                    hard_stop_price = round(sell_price * 1.05, 1)
                    stop_price = round(min_close_since_sell * 1.03, 1)
                    
                    if next_high >= hard_stop_price:
                        sell_trigger = True
                        sell_reason = "HARD_STOP_5%"
                        buyback_price = next_open if next_open >= hard_stop_price else hard_stop_price
                    elif trailing_active and (next_high >= stop_price):
                        sell_trigger = True
                        sell_reason = f"TRAILING_3%_ACTIVE({stop_price})"
                        buyback_price = next_open if next_open >= stop_price else stop_price
                    elif is_sim_end_day:
                        sell_trigger = True
                        sell_reason = "FINAL_BUYBACK"
                        buyback_price = df['Close'].iloc[i+1]

                    if sell_trigger:
                        profit = round(sell_price - buyback_price, 1)
                        total_profit += profit
                        trade_history.append({
                            "Date": next_date.date(), "Action": "BUYBACK",
                            "Price": buyback_price, "Reason": sell_reason, "Profit": profit
                        })
                        position = 0
                        sell_price = 0
                        min_close_since_sell = 9999999
                        trailing_active = False
                        holding_days = 0  # 【追加】買い戻し後はリセット[cite: 2]

        # --- 修正箇所：列名を明示的に指定してデータフレームを作成 ---[cite: 2]
        result_df = pd.DataFrame(trade_history, columns=["Date", "Action", "Price", "Reason", "Profit"])
        result_df.to_csv(f"{RESULT_DIR}/{ticker}_trades.csv", index=False)
        
        total_profit = round(total_profit, 1)
        
        # 修正箇所：Action列が確実に存在するため、安全にカウント可能[cite: 2]
        real_trade_count = len(result_df[result_df['Action'].isin(['SHORT_SELL', 'BUYBACK'])]) // 2
        
        summary_reports.append({
            "Ticker": ticker, "Total_Profit": total_profit, "Trade_Count": real_trade_count
        })
        print(f"◎ {ticker}: 完了 (損益 {total_profit:,.1f}円)")

    summary_df = pd.DataFrame(summary_reports)
    summary_df.to_csv(f"{RESULT_DIR}/overall_summary.csv", index=False)
    print(f"\n--- シミュレーション完了 ---")

if __name__ == "__main__":
    run_short_simulation_auto()