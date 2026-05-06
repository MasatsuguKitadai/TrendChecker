import pandas as pd
import os
import yfinance as yf

# --- 設定 ---
DATA_DIR = "calculated_data"
LONG_RESULT_DIR = "simulation_results"
SHORT_RESULT_DIR = "simulation_results_short"
ACTION_FILE = "simulation_results/todays_actions.csv"

def get_company_name(ticker):
    """yfinanceを使用して銘柄名を取得する"""
    try:
        t_code = ticker if ".T" in ticker else f"{ticker}.T"
        info = yf.Ticker(t_code).info
        return info.get('shortName') or info.get('longName') or ticker
    except:
        return ticker

def get_last_trade(dir_path, ticker):
    """シミュレーション結果の最終行を取得する"""
    trade_file = os.path.join(dir_path, f"{ticker}_trades.csv")
    if os.path.exists(trade_file):
        try:
            t_df = pd.read_csv(trade_file)
            if not t_df.empty:
                return t_df.iloc[-1]
        except:
            pass
    return None

def check_todays_action():
    all_files = [f for f in os.listdir(DATA_DIR) if f.endswith('_analyzed.csv')]
    if not all_files:
        print("× 解析済みデータが見つかりません。")
        return

    actions_list = []

    for file_name in all_files:
        ticker = file_name.replace("_analyzed.csv", "")
        df = pd.read_csv(os.path.join(DATA_DIR, file_name), index_col="Date", parse_dates=True)
        if df.empty or len(df) < 2:
            continue

        c = df.iloc[-1] # 本日のデータ
        p = df.iloc[-2] # 前日のデータ
        name = get_company_name(ticker)

        # 前日比（ギャップ）の計算
        gap_price = round(c['Close'] - p['Close'], 1)
        gap_percent = round((c['Close'] / p['Close'] - 1) * 100, 2)
        gap_text = f"{'+' if gap_price > 0 else ''}{gap_price} ({'+' if gap_percent > 0 else ''}{gap_percent}%)"

        ohlc_data = {
            "Ticker": ticker,
            "Name": name,
            "Open": c['Open'],
            "High": c['High'],
            "Low": c['Low'],
            "Close": c['Close'],
            "GapText": gap_text,
            "GapRaw": gap_price,
            "Action": "待機",
            "Type": "IDLE"
        }

        # シミュレーション結果の参照
        last_long = get_last_trade(LONG_RESULT_DIR, ticker)
        last_short = get_last_trade(SHORT_RESULT_DIR, ticker)

        # --- 1. 買い（ロング）の状態判定 ---
        if last_long is not None:
            if last_long['Action'] == "BUY_SIGNAL":
                ohlc_data["Action"] = f"翌日始値で新規買：{last_long['Reason']}"
                ohlc_data["Type"] = "NEW_LONG"
            
            elif last_long['Action'] == "HOLDING":
                t_df = pd.read_csv(os.path.join(LONG_RESULT_DIR, f"{ticker}_trades.csv"))
                buy_row = t_df[t_df['Action'] == 'BUY'].iloc[-1]
                buy_price = buy_row['Price']
                trade_date = pd.to_datetime(buy_row['Date'])
                
                # エントリー日からの経過日数を判定
                days_held = len(df.loc[trade_date:])
                
                if days_held == 1:
                    # 約定した当日の夜の判定（＝翌日は判定スキップして何もしない）
                    ohlc_data["Action"] = "スキップ"
                else:
                    # 2日目以降の通常の逆指値計算
                    max_c = df.loc[trade_date:, 'Close'].max()
                    stop = max(round(max_c * 0.95, 1), round(buy_price * 0.95, 1))
                    ohlc_data["Action"] = f"翌日逆指値：{stop}円"
                
                ohlc_data["Type"] = "HOLD_LONG"

        # --- 2. 売り（ショート）の状態判定 ---
        if last_short is not None:
            if last_short['Action'] == "SHORT_SIGNAL":
                ohlc_data["Action"] = f"翌日始値で新規売：{last_short['Reason']}"
                ohlc_data["Type"] = "NEW_SHORT"
            
            elif last_short['Action'] == "HOLDING":
                t_df = pd.read_csv(os.path.join(SHORT_RESULT_DIR, f"{ticker}_trades.csv"))
                sell_row = t_df[t_df['Action'] == 'SHORT_SELL'].iloc[-1]
                sell_price = sell_row['Price']
                trade_date = pd.to_datetime(sell_row['Date'])
                
                # エントリー日からの経過日数を判定
                days_held = len(df.loc[trade_date:])
                
                if days_held == 1:
                    # 約定した当日の夜の判定（＝翌日は判定スキップして何もしない）
                    ohlc_data["Action"] = "スキップ"
                else:
                    # 2日目以降の通常の逆指値計算
                    min_c = df.loc[trade_date:, 'Close'].min()
                    stop = min(round(min_c * 1.03, 1), round(sell_price * 1.05, 1))
                    ohlc_data["Action"] = f"翌日逆指値：{stop}円"
                    
                ohlc_data["Type"] = "HOLD_SHORT"

        actions_list.append(ohlc_data)

    # 結果の保存
    os.makedirs(os.path.dirname(ACTION_FILE), exist_ok=True)
    pd.DataFrame(actions_list).to_csv(ACTION_FILE, index=False)
    print(f"◎ アドバイザー指示書を更新しました。\n")

if __name__ == "__main__":
    check_todays_action()