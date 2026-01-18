import pandas as pd
import math
from datetime import datetime

def add_technical_indicators(df):
    """
    データフレームにテクニカル指標（MA, RSI, 出来高MA）を追加する
    (ここは変更なし)
    """
    if df is None or df.empty:
        return None
    
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA25'] = df['Close'].rolling(window=25).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-10))))
    
    df['VolMA5'] = df['Volume'].rolling(window=5).mean()
    
    return df

def get_latest_metrics(df, purchase_price, purchase_timestamp_str=None):
    """
    【修正版】購入日以降のデータに基づいて指標を取得する
    Args:
        df: 株価データ (60日分)
        purchase_price: 取得単価 (float)
        purchase_timestamp_str: ポートフォリオのID (文字列のタイムスタンプ)
    """
    if df is None or df.empty:
        return 0, 0, 0

    current_price = df['Close'].iloc[-1]
    
    # 1. 期間のフィルタリング（購入日以降のデータのみ抽出）
    target_df = df
    
    if purchase_timestamp_str:
        try:
            # ID(タイムスタンプ)を日付型に変換
            buy_date = datetime.fromtimestamp(float(purchase_timestamp_str)).date()
            
            # DataFrameのインデックス(日付)と比較してフィルタリング
            # ※df.index が timezone aware の場合に対応するため date() で比較
            mask = [d.date() >= buy_date for d in df.index]
            target_df = df[mask]
            
            # もし「今日買ったばかり」でデータ更新前などで空になる場合は、元のdfの最後尾を使う
            if target_df.empty:
                target_df = df.tail(1)
        except:
            # エラー時はフィルタリングせず全期間を使う（安全策）
            target_df = df

    # 2. 最高値の決定
    # 購入日以降の最高値を取得。
    # ただし、「購入直後に下がり続けている」場合は最高値が存在しないため、
    # 「取得単価」と「期間内最高値」の高い方を採用する（ここが重要）
    period_high = target_df['High'].max()
    
    # NaN対策（データ不足時）
    if pd.isna(period_high):
        recent_high = max(purchase_price, current_price)
    else:
        # トレール計算用の最高値は、「取得単価」を下回ってはいけない
        # (取得単価より下でトレールが発動するのはおかしいので)
        recent_high = max(purchase_price, period_high)

    # RSI（最新の値を使うので元のdfから取得）
    rsi = df['RSI'].iloc[-1] if 'RSI' in df.columns else 0
    
    return current_price, recent_high, rsi

def calculate_exit_strategy(price_buy, price_curr, price_high, stop_pct, trail_pct):
    """
    【Exit判定】利確・損切りのロジック
    (計算ロジック自体は変更なしだが、入力される price_high が適正化される)
    """
    profit_pct = ((price_curr - price_buy) / price_buy) * 100
    
    # 1. 基本防衛ライン（5%ルール）
    if profit_pct <= 5.0:
        base_line = price_buy * (1 - stop_pct)
        label = "損切り防衛"
    else:
        base_line = price_buy # 建値固定
        label = "建値固定(利益5%超)"
    
    # 2. トレールラインとの比較
    trail_line = price_high * (1 - trail_pct)
    
    # どちらか高い方を採用
    suggested_price = max(base_line, trail_line)
    
    # 3. 緊急判定
    is_emergency = False
    final_order_price = suggested_price
    
    if suggested_price >= price_curr:
        is_emergency = True
        final_order_price = price_curr * 0.985
        label = "成行推奨/緊急"

    return {
        "order_price": final_order_price,
        "raw_line": suggested_price,
        "label": label,
        "is_emergency": is_emergency,
        "profit_pct": profit_pct
    }

# Entry判定などの他関数はそのまま...
def analyze_entry_strategy(df):
    # ... (前回のコードと同じ)
    if df is None or df.empty: return 0, []
    # (省略)
    return 0, []

def calculate_position_size(total_capital, risk_pct, price_curr, stop_pct):
    # ... (前回のコードと同じ)
    # (省略)
    return 0