import pandas as pd
import math
from datetime import datetime

# ==========================================
# 1. テクニカル指標の計算
# ==========================================
def add_technical_indicators(df):
    """
    データフレームにテクニカル指標（MA, RSI, 出来高MA）を追加する
    長期判定用にMA75を追加
    """
    if df is None or df.empty:
        return None
    
    # 移動平均線
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA25'] = df['Close'].rolling(window=25).mean()
    df['MA75'] = df['Close'].rolling(window=75).mean() # 長期用に追加
    
    # RSI計算
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-10))))
    
    # 出来高移動平均
    df['VolMA5'] = df['Volume'].rolling(window=5).mean()
    
    return df

def get_latest_metrics(df, purchase_price, purchase_timestamp_str=None):
    """
    購入日以降のデータに基づいて指標を取得する（Exit判定用）
    """
    if df is None or df.empty:
        return 0, 0, 0, 0

    current_price = df['Close'].iloc[-1]
    ma75 = df['MA75'].iloc[-1] if 'MA75' in df.columns else 0 # MA75取得
    
    # 期間フィルタリング（購入日以降のみ対象）
    target_df = df
    if purchase_timestamp_str:
        try:
            buy_date = datetime.fromtimestamp(float(purchase_timestamp_str)).date()
            mask = [d.date() >= buy_date for d in df.index]
            filtered_df = df[mask]
            target_df = filtered_df if not filtered_df.empty else df.tail(1)
        except:
            pass

    # 最高値の決定（購入単価を下限とする）
    period_high = target_df['High'].max()
    
    if pd.isna(period_high):
        recent_high = max(purchase_price, current_price)
    else:
        recent_high = max(purchase_price, period_high)

    rsi = df['RSI'].iloc[-1] if 'RSI' in df.columns else 0
    
    return current_price, recent_high, rsi, ma75

# ==========================================
# 2. 売買判定ロジック
# ==========================================
def calculate_exit_strategy(price_buy, price_curr, price_high, ma75, stop_pct, trail_pct, mode="short"):
    """
    【Exit判定】利確・損切りのロジック
    Args:
        mode (str): "short" (短期) or "long" (長期/可変)
    """
    profit_pct = ((price_curr - price_buy) / price_buy) * 100
    label = ""
    used_trail_pct = trail_pct # デフォルトは設定値を使用
    
    # --- モード分岐 ---
    if mode == "long":
        # 【長期モード (案2: 利益バッファ活用)】
        # 利益の乗り具合でリスク許容度を自動調整
        
        if profit_pct < 10.0:
            # Zone 1: 含み益10%未満 -> 「短期モード」と同じ厳戒態勢
            label = "長期：育成中"
            used_trail_pct = trail_pct # 設定値(例:10%)そのまま
            
        elif 10.0 <= profit_pct < 30.0:
            # Zone 2: 含み益10-30% -> トレールを15%に広げて様子見
            label = "長期：安定期(トレール15%)"
            used_trail_pct = 0.15 
            
        else:
            # Zone 3: 含み益30%超 -> トレール20% ＆ MA75サポート
            label = "長期：収穫期(MA75/20%)"
            used_trail_pct = 0.20
    else:
        # 【短期モード】
        # 常にユーザー設定のトレール率を使用
        label = "短期トレード"

    # --- 共通計算ロジック ---
    
    # 1. 基本防衛ライン（損切り or 建値）
    if profit_pct <= 5.0:
        base_line = price_buy * (1 - stop_pct)
        if mode == "short": label += "/損切管理"
    else:
        base_line = price_buy # 建値撤退
        if mode == "short": label += "/建値防衛"
    
    # 2. トレールライン（最高値 - N%）
    trail_line = price_high * (1 - used_trail_pct)
    
    # 3. テクニカル指標ライン（長期モードのZone3のみ MA75 を考慮）
    ma_line = 0
    if mode == "long" and profit_pct >= 30.0:
        ma_line = ma75
    
    # すべてのラインの中で「最も高い価格」を逆指値とする
    suggested_price = max(base_line, trail_line, ma_line)
    
    # 緊急判定
    is_emergency = False
    final_order_price = suggested_price
    
    if suggested_price >= price_curr:
        is_emergency = True
        final_order_price = price_curr * 0.985
        label = "🚨 緊急脱出"

    return {
        "order_price": final_order_price,
        "raw_line": suggested_price,
        "label": label,
        "is_emergency": is_emergency,
        "profit_pct": profit_pct
    }

def analyze_entry_strategy(df):
    """
    【Entry判定】スコアリング (変更なし)
    """
    if df is None or df.empty:
        return 0, []

    rsi = df['RSI'].iloc[-1]
    ma5 = df['MA5'].iloc[-1]
    ma25 = df['MA25'].iloc[-1]
    vol_curr = df['Volume'].iloc[-1]
    vol_ma5 = df['VolMA5'].iloc[-1]
    
    score = 0
    reasons = []

    if rsi < 35:
        score += 50
        reasons.append("RSI低値圏")

    if len(df) >= 2:
        prev_ma5 = df['MA5'].iloc[-2]
        prev_ma25 = df['MA25'].iloc[-2]
        if ma5 > ma25 and prev_ma5 <= prev_ma25:
            score += 50
            reasons.append("ゴールデンクロス")

    if vol_ma5 > 0 and vol_curr > (vol_ma5 * 1.5):
        score += 20
        reasons.append("出来高急増")

    return score, reasons

# ==========================================
# 3. 資金管理ロジック
# ==========================================
def calculate_position_size(total_capital, risk_pct, price_curr, stop_pct):
    """
    【資金管理】リスクリワードに基づく推奨株数を計算する (変更なし)
    """
    if price_curr <= 0: return 0

    risk_limit = total_capital * (risk_pct / 100)
    dist = price_curr * stop_pct 
    
    if dist <= 0:
        risk_based_shares = 0
    else:
        risk_based_shares = risk_limit / dist
    
    budget_based_shares = total_capital / price_curr
    final_raw_shares = min(risk_based_shares, budget_based_shares)
    rec_shares = math.floor(final_raw_shares / 100) * 100
    
    return rec_shares