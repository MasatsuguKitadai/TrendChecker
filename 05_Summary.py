import pandas as pd
import os
import yfinance as yf
import importlib

# --- 設定 ---
DATA_DIR = "calculated_data"

# ★変更点：2系統のディレクトリをそれぞれ指定
FIXED_RESULT_DIR = "simulation_results_fixed"
ATR_RESULT_DIR = "simulation_results_atr"

# 出力先（06のダッシュボードが読み込む共通ファイル）
ACTION_FILE = "simulation_results/todays_actions.csv"

# =====================================================================
# ★【自動同期ロジック】03_Simulation の各ファイルから定数を動的に読み込む
# =====================================================================
# 1. 固定5%パラメータの同期
try:
    sim_fixed = importlib.import_module("03_Simulation_Fixed")
    PROFIT_TARGET_TRAILING = sim_fixed.PROFIT_TARGET_TRAILING
    HARD_STOP_LOSS = sim_fixed.HARD_STOP_LOSS
    TRAILING_STOP_LOSS = sim_fixed.TRAILING_STOP_LOSS
except:
    PROFIT_TARGET_TRAILING, HARD_STOP_LOSS, TRAILING_STOP_LOSS = 1.05, 0.95, 0.95

# 2. ATRパラメータの同期
try:
    sim_atr = importlib.import_module("03_Simulation_ATR")
    ATR_MULTI_STOP = sim_atr.ATR_MULTI_STOP
    ATR_MULTI_TRAIL = sim_atr.ATR_MULTI_TRAIL
    PROFIT_TARGET_ATR_RATIO = sim_atr.PROFIT_TARGET_ATR_RATIO
except:
    ATR_MULTI_STOP, ATR_MULTI_TRAIL, PROFIT_TARGET_ATR_RATIO = 2.0, 2.5, 1.5
# =====================================================================

def get_company_name(ticker):
    """yfinanceを使用して銘柄名を取得する"""
    try:
        t_code = ticker if ".T" in ticker else f"{ticker}.T"
        info = yf.Ticker(t_code).info
        return info.get('shortName') or info.get('longName') or ticker
    except:
        return ticker

def get_last_trade(dir_path, ticker):
    """指定したディレクトリのシミュレーション結果から最終行を取得する"""
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
    print("--- アクション指示書の生成（固定5% ＆ ATR 両対応） ---")

    for file_name in all_files:
        ticker = file_name.replace("_analyzed.csv", "")
        df = pd.read_csv(os.path.join(DATA_DIR, file_name), index_col="Date", parse_dates=True)
        if df.empty or len(df) < 2:
            continue

        c = df.iloc[-1] # 本日のデータ
        p = df.iloc[-2] # 前日のデータ
        name = get_company_name(ticker)

        # ATRのフォールバック計算
        if 'ATR' not in df.columns:
            high_low = df['High'] - df['Low']
            high_cp = (df['High'] - df['Close'].shift(1)).abs()
            low_cp = (df['Low'] - df['Close'].shift(1)).abs()
            tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
            df['ATR'] = tr.rolling(window=14).mean().round(1)
            c = df.iloc[-1]

        gap_price = round(c['Close'] - p['Close'], 1)
        gap_percent = round((c['Close'] / p['Close'] - 1) * 100, 2)
        gap_text = f"{'+' if gap_price > 0 else ''}{gap_price} ({'+' if gap_percent > 0 else ''}{gap_percent}%)"

        # ベースとなる共通データ
        ohlc_data = {
            "Ticker": ticker,
            "Name": name,
            "Open": c['Open'],
            "High": c['High'],
            "Low": c['Low'],
            "Close": c['Close'],
            "GapText": gap_text,
            "GapRaw": gap_price,
            "Action_Fixed": "待機",
            "Type_Fixed": "IDLE",
            "Action_ATR": "待機",
            "Type_ATR": "IDLE"
        }

        # ---------------------------------------------------
        # ① 【固定5%】のアクション判定
        # ---------------------------------------------------
        last_fixed = get_last_trade(FIXED_RESULT_DIR, ticker)
        if last_fixed is not None:
            if last_fixed['Action'] == "BUY_SIGNAL":
                ohlc_data["Action_Fixed"] = f"新規買：{last_fixed['Reason']}"
                ohlc_data["Type_Fixed"] = "NEW_LONG"
            elif last_fixed['Action'] == "HOLDING":
                t_df = pd.read_csv(os.path.join(FIXED_RESULT_DIR, f"{ticker}_trades.csv"))
                buy_row = t_df[t_df['Action'] == 'BUY'].iloc[-1]
                buy_price, trade_date = buy_row['Price'], pd.to_datetime(buy_row['Date'])
                days_held = len(df.loc[trade_date:])
                max_c = df.loc[trade_date:, 'Close'].max()
                
                if max_c >= buy_price * PROFIT_TARGET_TRAILING:  
                    stop = max(round(max_c * TRAILING_STOP_LOSS, 1), round(buy_price * HARD_STOP_LOSS, 1))
                    ohlc_data["Action_Fixed"] = f"トレイル：{stop}円"
                elif days_held == 1:
                    ohlc_data["Action_Fixed"] = "保持（約定日）"
                else:
                    stop = round(buy_price * HARD_STOP_LOSS, 1)
                    ohlc_data["Action_Fixed"] = f"ストップ：{stop}円"
                ohlc_data["Type_Fixed"] = "HOLD_LONG"

        # ---------------------------------------------------
        # ② 【ATR可変】のアクション判定
        # ---------------------------------------------------
        last_atr = get_last_trade(ATR_RESULT_DIR, ticker)
        if last_atr is not None:
            if last_atr['Action'] == "BUY_SIGNAL":
                ohlc_data["Action_ATR"] = f"新規買：{last_atr['Reason']}"
                ohlc_data["Type_ATR"] = "NEW_LONG"
            elif last_atr['Action'] == "HOLDING":
                t_df = pd.read_csv(os.path.join(ATR_RESULT_DIR, f"{ticker}_trades.csv"))
                buy_row = t_df[t_df['Action'] == 'BUY'].iloc[-1]
                buy_price, trade_date = buy_row['Price'], pd.to_datetime(buy_row['Date'])
                days_held = len(df.loc[trade_date:])
                max_c = df.loc[trade_date:, 'Close'].max()
                c_atr = c['ATR']
                
                if max_c >= buy_price + (c_atr * PROFIT_TARGET_ATR_RATIO):  
                    stop = max(round(max_c - (c_atr * ATR_MULTI_TRAIL), 1), round(buy_price - (c_atr * ATR_MULTI_STOP), 1))
                    ohlc_data["Action_ATR"] = f"トレイル：{stop}円"
                elif days_held == 1:
                    ohlc_data["Action_ATR"] = "保持（約定日）"
                else:
                    stop = round(buy_price - (c_atr * ATR_MULTI_STOP), 1)
                    ohlc_data["Action_ATR"] = f"ストップ：{stop}円"
                ohlc_data["Type_ATR"] = "HOLD_LONG"

        actions_list.append(ohlc_data)

    # 出力
    os.makedirs(os.path.dirname(ACTION_FILE), exist_ok=True)
    df_output = pd.DataFrame(actions_list)
    df_output = df_output.sort_values(by='Ticker').reset_index(drop=True)
    df_output.to_csv(ACTION_FILE, index=False)
    print(f"◎ アドバイザー指示書を更新しました (固定 ＆ ATR 両対応)。\n")

if __name__ == "__main__":
    check_todays_action()