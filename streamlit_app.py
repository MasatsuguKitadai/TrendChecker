import streamlit as st
import yfinance as yf
import pandas as pd
import json
import base64
import requests
import time
import os
import math
from datetime import datetime
from github import Github

# ==========================================
# 0. 初期設定 & CSS読み込み
# ==========================================
st.set_page_config(page_title="Trend Checker Pro v5.0", layout="wide")

def load_local_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# ==========================================
# 1. 認証機能
# ==========================================
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    if st.session_state.password_correct:
        return True

    login_area = st.empty()
    with login_area.container():
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        st.title("🔒 Trend Checker Pro")
        st.write("Mechanical Trading Engine v5.0")
        password_input = st.text_input("Password", type="password")
        if st.button("Login", type="primary", use_container_width=True):
            if password_input == st.secrets["PASSWORD"]:
                st.session_state.password_correct = True
                login_area.empty()
                st.rerun()
            else:
                st.error("パスワードが正しくありません")
        st.markdown('</div>', unsafe_allow_html=True)
    return False

# ==========================================
# 2. GitHubデータ同期
# ==========================================
def sync_github(portfolio_data=None, action="load"):
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["GITHUB_USERNAME"] + "/" + st.secrets["GITHUB_REPO_NAME"]
    FILE_PATH = st.secrets["DATA_FILE_PATH"]
    
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
    
    if action == "load":
        try:
            contents = repo.get_contents(FILE_PATH)
            return json.loads(base64.b64decode(contents.content).decode("utf-8"))
        except:
            return []
            
    if action == "save":
        # NaNなどを防ぐため、保存前にクリーニング
        clean_data = []
        for item in portfolio_data:
            # 必須項目の保持と数値型の正規化
            clean_item = item.copy()
            clean_data.append(clean_item)
            
        json_content = json.dumps(clean_data, ensure_ascii=False, indent=4)
        try:
            contents = repo.get_contents(FILE_PATH)
            repo.update_file(contents.path, f"Sync: {datetime.now()}", json_content, contents.sha)
            st.toast("☁️ Sync Completed", icon="✅")
        except:
            repo.create_file(FILE_PATH, "Initial setup", json_content)
            st.toast("☁️ Created New Cloud File", icon="✅")
    return portfolio_data

# ==========================================
# 3. 分析エンジン（機能強化版）
# ==========================================
@st.cache_data(ttl=3600)
def fetch_stock_name(ticker):
    try:
        return yf.Ticker(ticker).info.get('shortName') or ticker
    except:
        return ticker

def get_technical_analysis(ticker):
    try:
        # 出来高も含めて取得
        df = yf.Ticker(ticker).history(period="60d")
        if df.empty: return None
        
        # 移動平均線
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA25'] = df['Close'].rolling(window=25).mean()
        
        # RSI計算
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-10))))
        
        # 出来高分析 (Volume Analysis)
        df['VolMA5'] = df['Volume'].rolling(window=5).mean()
        
        return df
    except Exception as e:
        return None

# ==========================================
# 4. メインアプリケーション
# ==========================================
def main():
    if not check_password(): return
    load_local_css("style.css")
    
    if 'portfolio' not in st.session_state:
        st.session_state.portfolio = sync_github(action="load")

    st.title("📈 Trend Checker Pro v5.0")

    # --- サイドバー：設定と資金管理 ---
    with st.sidebar:
        st.header("💰 資金管理 (Money Mgmt)")
        total_capital = st.number_input("総投資資金 (円)", value=1000000, step=100000)
        risk_per_trade = st.slider("1トレード許容リスク (%)", 0.5, 5.0, 2.0)
        
        st.divider()
        st.header("⚙️ デフォルト・ルール")
        st.caption("※各銘柄ごとの個別設定がない場合に適用")
        default_stop_pct = st.slider("損切り基準 (%)", 1, 15, 5) / 100
        default_trail_pct = st.slider("利確トレール (%)", 1, 20, 10) / 100
        
        st.divider()
        st.header("➕ 新規銘柄追加")
        with st.form("add_stock_form", clear_on_submit=True):
            t_code = st.text_input("銘柄コード (例: 7203.T)")
            t_status = st.selectbox("カテゴリ", ["保有株 (Exit監視)", "監視株 (Entry判定)"])
            t_price = st.number_input("取得/目安単価", min_value=0.0)
            t_shares = st.number_input("持ち株数", min_value=0, step=100, value=100)
            if st.form_submit_button("保存"):
                if t_code:
                    name = fetch_stock_name(t_code)
                    st.session_state.portfolio.append({
                        "id": str(datetime.now().timestamp()),
                        "ticker": t_code, 
                        "name": name, 
                        "price": t_price,
                        "shares": t_shares,
                        "status": "holding" if "保有" in t_status else "watching",
                        # 個別設定用フィールド (Noneならデフォルト使用)
                        "custom_stop": None,
                        "custom_trail": None
                    })
                    sync_github(st.session_state.portfolio, action="save")
                    st.rerun()

    # --- データ管理エディタ（パラメータ個別調整機能付き） ---
    with st.expander("🛠️ データ管理・パラメータ個別調整", expanded=False):
        st.info("💡 「Stop %」「Trail %」に数値を入力すると、その銘柄専用のルールが適用されます（空欄なら全体設定を使用）。ボラティリティに合わせて調整してください。")
        
        # データフレーム変換と表示用整形
        df_editor = pd.DataFrame(st.session_state.portfolio)
        
        # 新しい項目の列がない場合の互換性維持
        if 'custom_stop' not in df_editor.columns: df_editor['custom_stop'] = None
        if 'custom_trail' not in df_editor.columns: df_editor['custom_trail'] = None
        if 'shares' not in df_editor.columns: df_editor['shares'] = 0

        edited_df = st.data_editor(
            df_editor, 
            num_rows="dynamic", 
            use_container_width=True,
            column_config={
                "ticker": "Ticker",
                "name": "Name",
                "status": st.column_config.SelectboxColumn("Status", options=["holding", "watching"]),
                "price": st.column_config.NumberColumn("Price", format="%.1f"),
                "shares": st.column_config.NumberColumn("Shares", min_value=0, step=1),
                "custom_stop": st.column_config.NumberColumn("Stop % (個別)", min_value=1, max_value=20, help="個別損切り設定(%)。空欄でデフォルト使用"),
                "custom_trail": st.column_config.NumberColumn("Trail % (個別)", min_value=1, max_value=30, help="個別トレール設定(%)。空欄でデフォルト使用"),
                "id": None # IDは隠す
            }
        )
        if st.button("クラウド保存"):
            # NaNをNoneに変換してから保存
            st.session_state.portfolio = json.loads(edited_df.to_json(orient="records"))
            sync_github(st.session_state.portfolio, action="save")
            st.rerun()

    # --- タブ表示 ---
    tab1, tab2 = st.tabs(["🚀 保有銘柄 (Exit)", "🔍 監視銘柄 (Entry)"])

    # === タブ1: 保有銘柄 ===
    with tab1:
        holdings = [s for s in st.session_state.portfolio if s.get("status") == "holding"]
        
        # 資産集計
        total_market_value = 0
        
        for s in holdings:
            df = get_technical_analysis(s['ticker'])
            if df is None: continue
            
            curr = df['Close'].iloc[-1]
            high = df['High'].max() # 過去60日高値
            rsi = df['RSI'].iloc[-1]
            shares = s.get('shares', 0)
            
            # 個別設定 または デフォルト設定 の適用
            # データフレーム経由だとNaNが入る可能性があるためチェック
            p_stop = s.get('custom_stop')
            p_trail = s.get('custom_trail')
            
            applied_stop = (p_stop / 100) if (p_stop is not None and p_stop > 0) else default_stop_pct
            applied_trail = (p_trail / 100) if (p_trail is not None and p_trail > 0) else default_trail_pct
            
            # 計算
            profit_pct = ((curr - s['price']) / s['price']) * 100
            profit_amt = (curr - s['price']) * shares
            market_val = curr * shares
            total_market_value += market_val
            
            stop_line = s['price'] * (1 - applied_stop)
            trail_line = high * (1 - applied_trail)
            
            # 表示作成
            with st.expander(f"【 {s['ticker']} 】{s['name']} / {market_val:,.0f}円 ({profit_pct:+.1f}%)", expanded=True):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("取得単価", f"{s['price']:,.0f}", help=f"損切り設定: -{applied_stop*100:.1f}%")
                c2.metric("現在価格", f"{curr:,.0f}", delta=f"{curr-s['price']:+.0f}")
                c3.metric("株数 / 評価損益", f"{shares}", f"{profit_amt:+,.0f}円")
                c4.metric("最高値 (60d)", f"{high:,.0f}", help=f"トレール設定: -{applied_trail*100:.1f}%")

                # 判定ロジック
                # 1. 損切りライン割れ
                if curr <= stop_line:
                    st.markdown(f'''
                    <div class="status-box status-error">
                        <b>🚨 損切り警告 (STOP LOSS)</b><br>
                        現在値 {curr:,.0f} ≦ 損切目安 {stop_line:,.0f}<br>
                        (許容リスク -{applied_stop*100:.1f}% を超過)
                    </div>''', unsafe_allow_html=True)
                
                # 2. トレールライン割れ（利確）
                elif curr <= trail_line and curr > s['price']:
                    st.markdown(f'''
                    <div class="status-box status-warning">
                        <b>💰 利確確定 (TAKE PROFIT)</b><br>
                        現在値 {curr:,.0f} ≦ トレール目安 {trail_line:,.0f}<br>
                        (最高値から -{applied_trail*100:.1f}% 下落)
                    </div>''', unsafe_allow_html=True)
                
                # 3. ホールド
                else:
                    st.markdown(f'<div class="status-box status-success">✅ ホールド継続 (含み益推移中)</div>', unsafe_allow_html=True)

                # 過熱感チェック
                if rsi >= 80:
                    st.markdown(f'<div class="overheat-box">🔥 加熱注意 (RSI: {rsi:.1f})</div>', unsafe_allow_html=True)
                
                if st.button("削除 (売却済)", key=f"del_{s['id']}"):
                    st.session_state.portfolio = [x for x in st.session_state.portfolio if x['id'] != s['id']]
                    sync_github(st.session_state.portfolio, action="save")
                    st.rerun()

        st.caption(f"ポートフォリオ時価総額: {total_market_value:,.0f} 円")

    # === タブ2: 監視銘柄 (Entry & 資金管理) ===
    with tab2:
        watchings = [s for s in st.session_state.portfolio if s.get("status") == "watching"]
        
        # 資金管理情報の表示
        cash_position = total_capital - total_market_value
        st.markdown(f"#### 🏦 資金管理状況")
        m1, m2, m3 = st.columns(3)
        m1.metric("総資金", f"{total_capital:,.0f}円")
        m2.metric("現在余力 (Cash)", f"{cash_position:,.0f}円")
        risk_amt = total_capital * (risk_per_trade / 100)
        m3.metric("1トレード許容損失", f"{risk_amt:,.0f}円", f"総資金の {risk_per_trade}%")
        st.divider()

        for s in watchings:
            df = get_technical_analysis(s['ticker'])
            if df is None: continue
            
            curr = df['Close'].iloc[-1]
            rsi = df['RSI'].iloc[-1]
            ma5 = df['MA5'].iloc[-1]
            ma25 = df['MA25'].iloc[-1]
            vol_curr = df['Volume'].iloc[-1]
            vol_ma5 = df['VolMA5'].iloc[-1]

            # --- スコアリングロジック ---
            score = 0
            reasons = []

            # 1. RSI (売られすぎ)
            if rsi < 30: 
                score += 40
                reasons.append("RSI底値圏")
            elif rsi < 40:
                score += 20

            # 2. ゴールデンクロス (トレンド転換)
            # 直近でMA5がMA25を上回っている、かつ前日は下回っていた（クロス発生）
            prev_ma5 = df['MA5'].iloc[-2]
            prev_ma25 = df['MA25'].iloc[-2]
            if ma5 > ma25 and prev_ma5 <= prev_ma25:
                score += 30
                reasons.append("ゴールデンクロス発生")
            elif ma5 > ma25:
                score += 10 # 既に上昇トレンド

            # 3. 出来高急増 (Selling Climax / Buying Pressure)
            if vol_ma5 > 0 and vol_curr > (vol_ma5 * 2.0):
                score += 30
                reasons.append("出来高急増(2倍超)")
            elif vol_ma5 > 0 and vol_curr > (vol_ma5 * 1.5):
                score += 10

            # --- ポジションサイジング計算 ---
            # 損切り幅をデフォルト設定と仮定して計算
            estimated_stop_loss_pct = s.get('custom_stop') if s.get('custom_stop') else (default_stop_pct * 100)
            stop_price_dist = curr * (estimated_stop_loss_pct / 100)
            
            # リスクベースの推奨株数 = 許容リスク額 / 1株あたりの損切り幅
            if stop_price_dist > 0:
                rec_shares = math.floor(risk_amt / stop_price_dist)
                # 単元株(100)で丸める場合
                rec_shares_100 = math.floor(rec_shares / 100) * 100
            else:
                rec_shares_100 = 0
                
            buy_cost = rec_shares_100 * curr

            # カード表示
            with st.expander(f"【 {s['ticker']} 】{s['name']} / スコア：{score}点", expanded=True):
                c1, c2, c3 = st.columns(3)
                c1.metric("現在価格", f"{curr:,.0f}")
                c2.metric("RSI (14)", f"{rsi:.1f}")
                
                vol_ratio = vol_curr / vol_ma5 if vol_ma5 > 0 else 0
                c3.metric("出来高 / 平均比", f"{vol_curr/1000:.1f}k", f"{vol_ratio:.1f}倍")

                # エントリー判定
                if score >= 50:
                    reason_text = " / ".join(reasons)
                    st.markdown(f'<div class="status-box status-success">🚀 買いシグナル点灯 ({reason_text})</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="status-box status-info">💤 監視継続</div>', unsafe_allow_html=True)

                # 資金管理アドバイス
                st.info(f"""
                **👮 ポジションサイジング推奨**
                許容リスク({risk_per_trade}%)を守るための上限株数は **{rec_shares_100:,}株** です。
                (予想取得コスト: {buy_cost:,.0f}円 / 損切設定: -{estimated_stop_loss_pct}%)
                """)
                if buy_cost > cash_position:
                    st.caption(f"⚠️ 注意: 余力不足です (不足: {buy_cost - cash_position:,.0f}円)")

                # アクションボタン
                if st.button(f"保有へ移行", key=f"mov_{s['id']}"):
                    for p in st.session_state.portfolio:
                        if p['id'] == s['id']:
                            p['status'] = 'holding'
                            p['price'] = curr
                            p['shares'] = rec_shares_100 if rec_shares_100 > 0 else 100
                    sync_github(st.session_state.portfolio, action="save")
                    st.rerun()

if __name__ == "__main__":
    main()