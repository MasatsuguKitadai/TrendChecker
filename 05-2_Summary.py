# fileName: 05_Summary.py
import pandas as pd
import os
import yfinance as yf
import importlib  # 数字から始まるファイルからインポートするために使用

# --- 設定 ---
DATA_DIR = "calculated_data"
LONG_RESULT_DIR = "simulation_results"
SHORT_RESULT_DIR = "simulation_results_short"
ACTION_FILE = "simulation_results/todays_actions.csv"

# =====================================================================
# ★【自動同期ロジック】ロング・ショート両方の03スクリプトからルールを動的読込
# =====================================================================
# 1. ロングルールの同期
try:
    sim_03 = importlib.import_module("03_Simulation")
    PROFIT_TARGET_TRAILING_LONG = sim_03.PROFIT_TARGET_TRAILING  # 初期値: 1.05
    HARD_STOP_LOSS_LONG = sim_03.HARD_STOP_LOSS                  # 初期値: 0.95
    TRAILING_STOP_LOSS_LONG = sim_03.TRAILING_STOP_LOSS          # 初期値: 0.95
    print(f"◎ 03_Simulation.py からロング・ルールを自動同期しました。")
    print(f"   (利確トリガー: {PROFIT_TARGET_TRAILING_LONG}, 損切: {HARD_STOP_LOSS_LONG}, トレイル: {TRAILING_STOP_LOSS_LONG})")
except Exception as e:
    PROFIT_TARGET_TRAILING_LONG = 1.05
    HARD_STOP_LOSS_LONG = 0.95
    TRAILING_STOP_LOSS_LONG = 0.95
    print(f"※ ロング設定の同期に失敗したため、デフォルト値で動作します。理由: {e}")

# 2. ショートルールの同期
try:
    sim_03_short = importlib.import_module("03-2_Simulation_Short")
    PROFIT_TARGET_TRAILING_SHORT = sim_03_short.PROFIT_TARGET_TRAILING  # 初期値: 0.95
    HARD_STOP_LOSS_SHORT = sim_03_short.HARD_STOP_LOSS                  # 初期値: 1.05
    TRAILING_STOP_LOSS_SHORT = sim_03_short.TRAILING_STOP_LOSS          # 初期値: 1.05
    print(f"◎ 03-2_Simulation_Short.py からショート・ルールを自動同期しました。")
    print(f"   (利確トリガー: {PROFIT_TARGET_TRAILING_SHORT}, 損切: {HARD_STOP_LOSS_SHORT}, トレイル: {TRAILING_STOP_LOSS_SHORT})")
except Exception as e:
    PROFIT_TARGET_TRAILING_SHORT = 0.95
    HARD_STOP_LOSS_SHORT = 1.05
    TRAILING_STOP_LOSS_SHORT = 1.05
    print(f"※ ショート設定の同期に失敗したため、デフォルト値で動作します。理由: {e}")
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

        # 前日比（ギャップ）を計算
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

        # --- シミュレーション結果の参照（ロング） ---
        last_long = get_last_trade(LONG_RESULT_DIR, ticker)
        if last_long is not None:
            if last_long['Action'] == "BUY_SIGNAL":
                ohlc_data["Action"] = f"新規買：{last_long['Reason']}"
                ohlc_data["Type"] = "NEW_LONG"
            elif last_long['Action'] == "HOLDING":
                t_df = pd.read_csv(os.path.join(LONG_RESULT_DIR, f"{ticker}_trades.csv"))
                buy_row = t_df[t_df['Action'] == 'BUY'].iloc[-1]
                buy_price, trade_date = buy_row['Price'], pd.to_datetime(buy_row['Date'])
                days_held = len(df.loc[trade_date:])
                
                max_c = df.loc[trade_date:, 'Close'].max()
                
                if max_c >= buy_price * PROFIT_TARGET_TRAILING_LONG:  
                    stop = max(round(max_c * TRAILING_STOP_LOSS_LONG, 1), round(buy_price * HARD_STOP_LOSS_LONG, 1))
                    ohlc_data["Action"] = f"逆指値：{stop}円"
                elif days_held == 1:
                    ohlc_data["Action"] = "保持（約定日）"
                else:
                    stop = round(buy_price * HARD_STOP_LOSS_LONG, 1)
                    ohlc_data["Action"] = f"逆指値：{stop}円"
                    
                ohlc_data["Type"] = "HOLD_LONG"

        # --- シミュレーション結果の参照（ショート） ---
        last_short = get_last_trade(SHORT_RESULT_DIR, ticker)
        if last_short is not None:
            if last_short['Action'] == "SHORT_SIGNAL":
                ohlc_data["Action"] = f"新規売：{last_short['Reason']}"
                ohlc_data["Type"] = "NEW_SHORT"
            elif last_short['Action'] == "HOLDING":
                t_df = pd.read_csv(os.path.join(SHORT_RESULT_DIR, f"{ticker}_trades.csv"))
                sell_row = t_df[t_df['Action'] == 'SHORT_SELL'].iloc[-1]
                sell_price, trade_date = sell_row['Price'], pd.to_datetime(sell_row['Date'])
                days_held = len(df.loc[trade_date:])
                
                if days_held == 1:
                    ohlc_data["Action"] = "保持（約定日）"
                else:
                    # 空売り（約定日）以降の最低終値を取得
                    min_c = df.loc[trade_date:, 'Close'].min()
                    
                    # ★【ショート専用ロジック：自動同期した変数に置き換え＆反転計算】
                    if min_c <= sell_price * PROFIT_TARGET_TRAILING_SHORT:  
                        # 最安値から5%上昇、またはエントリーから5%上昇の低い方をブレイクで買い戻し
                        stop = min(round(min_c * TRAILING_STOP_LOSS_SHORT, 1), round(sell_price * HARD_STOP_LOSS_SHORT, 1))
                        ohlc_data["Action"] = f"逆指値：{stop}円"
                    else:
                        # まだ利確トリガーを引いていない場合は初期損切りライン
                        stop = round(sell_price * HARD_STOP_LOSS_SHORT, 1)
                        ohlc_data["Action"] = f"逆指値：{stop}円"
                
                ohlc_data["Type"] = "HOLD_SHORT"

        actions_list.append(ohlc_data)

    os.makedirs(os.path.dirname(ACTION_FILE), exist_ok=True)
    pd.DataFrame(actions_list).to_csv(ACTION_FILE, index=False)
    print(f"◎ アドバイザー指示書を更新しました (ロング/ショート両対応・前日比データ含む)。\n")

if __name__ == "__main__":
    check_todays_action()