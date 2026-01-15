import streamlit as st
import yfinance as yf
import pandas as pd
import json
import base64
import os
import math
from datetime import datetime
from github import Github

# ==========================================
# 0. 基本設定 & ロジック関数
# ==========================================
st.set_page_config(page_title="Trend Checker Pro v5.5", layout="wide")

def load_css(file_name):
    """CSSファイルを読み込んで適用する"""
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

def calculate_exit_strategy(price_buy, price_curr, price_high, stop_pct, trail_pct):
    """
    利確・損切りのロジックを一括計算する純粋関数
    
    Args:
        price_buy: 取得単価
        price_curr: 現在価格
        price_high: 直近最高値
        stop_pct: 損切り率 (例: 0.05)
        trail_pct: トレール率 (例: 0.10)
    Returns:
        dict: 計算結果と表示用ラベル情報
    """
    profit_pct = ((price_curr - price_buy) / price_buy) * 100
    
    # 1. 基本防衛ラインの決定
    # 利益が5%以下のうちは「損切り設定」に従う。5%を超えたら「建値（買値）」を最低ラインにする
    if profit_pct <= 5.0:
        base_line = price_buy * (1 - stop_pct)
        label = "損切り防衛"
    else:
        base_line = price_buy # 建値固定
        label = "建値固定(利益5%超)"
    
    # 2. トレールラインとの比較
    # 最高値から一定％引いた価格が、基本ラインより高ければそちらを採用（利益確保）
    trail_line = price_high * (1 - trail_pct)
    suggested_price = max(base_line, trail_line)
    
    # 3. 緊急判定（現在値が逆指値に近い、または下回っている場合）
    # 逆指値は現在値より安くないと注文が入らないため、現在値を下回っている場合は強制的に下に置く
    is_emergency = False
    final_order_price = suggested_price
    
    if suggested_price >= price_curr:
        is_emergency = True
        final_order_price = price_curr * 0.985 # 現在値の1.5%下に設定
        label = "成行推奨/緊急"

    return {
        "order_price": final_order_price,
        "raw_line": suggested_price,
        "label": label,
        "is_emergency": is_emergency,
        "profit_pct": profit_pct
    }

# ==========================================
# 1. 認証 & GitHub同期
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
        st.write("Mechanical Trading Engine v5.5")
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

def sync_github(data=None, action="load"):
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = f"{st.secrets['GITHUB_USERNAME']}/{st.secrets['GITHUB_REPO_NAME']}"
    FILE_PATH = st.secrets["DATA_FILE_PATH"]
    
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
    except Exception as e:
        st.error(f"GitHub接続エラー: {e}")
        return {"portfolio": [], "settings": {}}
    
    if action == "load":
        try:
            contents = repo.get_contents(FILE_PATH)
            decoded = base64.b64decode(contents.content).decode("utf-8")
            loaded_data = json.loads(decoded)
            
            # データの正規化（リスト形式で保存されていた場合の対応）
            if isinstance(loaded_data, list):
                return {"portfolio": loaded_data, "settings": {"total_capital": 1000000, "risk_per_trade": 2.0}}
            return loaded_data
        except:
            return {"portfolio": [], "settings": {"total_capital": 1000000, "risk_per_trade": 2.0}}
            
    if action == "save":
        json_content = json.dumps(data, ensure_ascii=False, indent=4)
        try:
            contents = repo.get_contents(FILE_PATH)
            repo.update_file(contents.path, f"Sync: {datetime.now()}", json_content, contents.sha)
            st.toast("☁️ クラウド同期完了", icon="✅")
        except:
            repo.create_file(FILE_PATH, "Initial setup", json_content)
            st.toast("☁️ 新規ファイル作成", icon="✅")
    return data

@st.cache_data(ttl=3600)
def fetch_stock_name(ticker):
    try:
        return yf.Ticker(ticker).info.get('shortName') or ticker
    except:
        return ticker

@st.cache_data(ttl=3600)
def get_technical_analysis(ticker):
    try:
        df = yf.Ticker(ticker).history(period="60d")
        if df.empty: return None
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA25'] = df['Close'].rolling(window=25).mean()
        
        # RSI計算
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-10))))
        
        df['VolMA5'] = df['Volume'].rolling(window=5).mean()
        return df
    except: return None

# ==========================================
# 2. メインアプリケーション
# ==========================================
def main():
    if not check_password(): return
    load_css("style.css")
    
    if 'data' not in st.session_state:
        st.session_state.data = sync_github(action="load")
    
    data = st.session_state.data
    settings = data.get("settings", {"total_capital": 1000000, "risk_per_trade": 2.0})

    st.title("📈 Trend Checker Pro v5.5")

    # --- サイドバー：設定と登録 ---
    with st.sidebar:
        st.header("💰 資金管理設定")
        new_capital = st.number_input("総投資資金 (円)", value=int(settings.get("total_capital", 1000000)), step=100000)
        new_risk = st.slider("1トレード許容リスク (%)", 0.5, 5.0, float(settings.get("risk_per_trade", 2.0)))
        
        if st.button("資金設定を保存", use_container_width=True):
            st.session_state.data["settings"] = {"total_capital": new_capital, "risk_per_trade": new_risk}
            sync_github(st.session_state.data, action="save")
            st.rerun()
            
        st.divider()
        st.header("⚙️ 機械的ルール")
        default_stop_pct = st.sidebar.slider("損切り基準 (%)", 1, 15, 5) / 100
        default_trail_pct = st.sidebar.slider("利確トレール (%)", 1, 20, 10) / 100
        
        st.divider()
        st.header("➕ 銘柄追加")
        with st.form("add_stock_form", clear_on_submit=True):
            t_code = st.text_input("銘柄コード (例: 202A.T)")
            t_status = st.selectbox("カテゴリ", ["保有株 (Exit監視)", "監視株 (Entry判定)"])
            t_price = st.number_input("取得/目安単価", min_value=0.0)
            t_shares = st.number_input("株数", min_value=0, step=100, value=100)
            if st.form_submit_button("銘柄を追加"):
                if t_code:
                    name = fetch_stock_name(t_code)
                    st.session_state.data["portfolio"].append({
                        "id": str(datetime.now().timestamp()),
                        "ticker": t_code, "name": name, "price": t_price,
                        "shares": t_shares, 
                        "status": "holding" if "保有" in t_status else "watching",
                        "custom_stop": None, "custom_trail": None
                    })
                    sync_github(st.session_state.data, action="save")
                    st.rerun()

        # --- 新機能: JSONインポート ---
        st.divider()
        st.header("📂 データインポート")
        uploaded_file = st.file_uploader("JSONファイルをアップロード", type=["json"], help="portfolio.jsonをアップロードして一括更新します")
        
        if uploaded_file is not None:
            try:
                import_data = json.load(uploaded_file)
                
                # フォーマットの自動判定と読み込み
                # ケース1: 単なる銘柄リスト [ {...}, {...} ]
                if isinstance(import_data, list):
                    st.session_state.data["portfolio"] = import_data
                    
                # ケース2: 完全なデータセット { "portfolio": [...], "settings": {...} }
                elif isinstance(import_data, dict) and "portfolio" in import_data:
                    st.session_state.data["portfolio"] = import_data["portfolio"]
                    if "settings" in import_data:
                        st.session_state.data["settings"] = import_data["settings"]
                
                # 保存してリロード
                sync_github(st.session_state.data, action="save")
                st.success("インポート完了！")
                st.rerun()
            except Exception as e:
                st.error(f"読み込みエラー: {e}")

    # --- データエディタ ---
    with st.expander("🛠️ ポートフォリオ一括管理 (JSON編集)", expanded=False):
        df_editor = pd.DataFrame(st.session_state.data["portfolio"])
        # 必要なカラムがなければ追加
        for col in ['shares', 'custom_stop', 'custom_trail']:
            if col not in df_editor.columns: df_editor[col] = None
            
        edited_df = st.data_editor(df_editor, num_rows="dynamic", use_container_width=True)
        
        if st.button("変更をクラウド保存", use_container_width=True):
            st.session_state.data["portfolio"] = edited_df.to_dict(orient="records")
            sync_github(st.session_state.data, action="save")
            st.rerun()

    # --- メインタブ ---
    tab1, tab2 = st.tabs(["🚀 保有銘柄 (Exit)", "🔍 監視銘柄 (Entry)"])

    # --- タブ1: 保有銘柄 ---
    with tab1:
        current_holdings = [s for s in st.session_state.data["portfolio"] if s.get("status") == "holding"]
        total_market_value = 0
        
        if not current_holdings:
            st.info("保有銘柄がありません。")
        else:
            st.markdown("### 📋 本日の逆指値注文ガイド")
            st.caption("朝、証券アプリで以下の「トリガー価格」に逆指値（成行売り）を設定してください。")
            
            # カードグリッド表示
            guide_cols = st.columns(len(current_holdings) if len(current_holdings) < 4 else 4)
            
            for idx, s in enumerate(current_holdings):
                df = get_technical_analysis(s['ticker'])
                if df is None: continue
                
                curr, high = df['Close'].iloc[-1], df['High'].max()
                
                # 個別設定があれば優先、なければ全体設定を使用
                p_stop = s.get('custom_stop')
                p_trail = s.get('custom_trail')
                applied_stop = (p_stop / 100) if (pd.notnull(p_stop) and p_stop > 0) else default_stop_pct
                applied_trail = (p_trail / 100) if (pd.notnull(p_trail) and p_trail > 0) else default_trail_pct
                
                # ロジック計算
                strategy = calculate_exit_strategy(
                    s['price'], curr, high, applied_stop, applied_trail
                )
                
                # CSSクラスの決定
                card_class = "bg-emergency" if strategy['is_emergency'] else ("bg-safe" if strategy['profit_pct'] > 5 else "bg-normal")
                label_class = "card-label-red" if strategy['is_emergency'] else "card-label-green"
                
                # HTML生成（CSSクラス使用）
                with guide_cols[idx % 4]:
                    st.markdown(f"""
                    <div class="guide-card {card_class}">
                        <div class="card-header">
                            <span class="card-ticker">{s['ticker']}</span>
                            <span class="{label_class}">{strategy['label']}</span>
                        </div>
                        <div class="card-name">{s.get('name', s['ticker'])}</div>
                        <div class="card-price-area">
                            {strategy['order_price']:,.0f} <span class="card-price-unit">円以下で売</span>
                        </div>
                        <div class="card-footer">
                            建値: {s['price']:,.0f}円<br>
                            現在: {curr:,.1f} ({strategy['profit_pct']:+.1f}%)
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                total_market_value += (curr * s.get('shares', 0))

            st.divider()

            # 詳細リスト
            for s in current_holdings:
                df = get_technical_analysis(s['ticker'])
                if df is None: continue
                curr, high, rsi = df['Close'].iloc[-1], df['High'].max(), df['RSI'].iloc[-1]
                
                p_stop = s.get('custom_stop')
                p_trail = s.get('custom_trail')
                applied_stop = (p_stop / 100) if (pd.notnull(p_stop) and p_stop > 0) else default_stop_pct
                applied_trail = (p_trail / 100) if (pd.notnull(p_trail) and p_trail > 0) else default_trail_pct
                
                strategy = calculate_exit_strategy(s['price'], curr, high, applied_stop, applied_trail)
                final_line = strategy['raw_line']
                
                with st.expander(f"【{s['ticker']}】{s.get('name', '')}", expanded=True):
                    c1, c2, c3, c4, c5 = st.columns(5)
                    c1.metric("取得単価", f"{s['price']:,.1f}")
                    c2.metric("現在価格", f"{curr:,.1f}", delta=f"{curr-s['price']:+.1f}")
                    c3.metric("株数 / 評価額", f"{s.get('shares', 0):,.0f}", f"{curr * s.get('shares', 0):,.0f}円")
                    c4.metric("5日最高値", f"{high:,.1f}")
                    
                    # 判定バッジ
                    if curr <= final_line:
                        label_text = "🚨 撤退ライン通過" if strategy['profit_pct'] <= 5.0 else "💰 利確ライン通過"
                        status_class = "status-error"
                    else:
                        label_text = "✅ ホールド継続"
                        status_class = "status-success"
                        
                    c5.markdown(f'<div class="status-box {status_class}">{label_text} ({final_line:,.0f}円)</div>', unsafe_allow_html=True)
                    
                    if rsi >= 80:
                        st.markdown(f'<div class="overheat-box">🔥 超過熱 (RSI: {rsi:.1f}) | 追撃厳禁</div>', unsafe_allow_html=True)

                    if st.button("銘柄を削除", key=f"del_{s['id']}"):
                        st.session_state.data["portfolio"] = [x for x in st.session_state.data["portfolio"] if x['id'] != s['id']]
                        sync_github(st.session_state.data, action="save")
                        st.rerun()

    # --- タブ2: 監視銘柄 ---
    with tab2:
        current_watchings = [s for s in st.session_state.data["portfolio"] if s.get("status") == "watching"]
        cash_pos = new_capital - total_market_value
        risk_limit = new_capital * (new_risk / 100)
        
        st.markdown(f"#### 🏦 買付余力: {cash_pos:,.0f}円 / 総資産: {new_capital:,.0f}円")
        
        if not current_watchings:
            st.info("監視中の銘柄はありません。サイドバーから追加してください。")

        for s in current_watchings:
            df = get_technical_analysis(s['ticker'])
            if df is None: continue
            
            curr, rsi = df['Close'].iloc[-1], df['RSI'].iloc[-1]
            ma5, ma25 = df['MA5'].iloc[-1], df['MA25'].iloc[-1]
            vol_curr, vol_ma5 = df['Volume'].iloc[-1], df['VolMA5'].iloc[-1]
            
            # 簡易スコアリング
            score = 0
            # RSIが低い（売られすぎ）
            if rsi < 35: score += 50
            # ゴールデンクロス（直近でMA5がMA25を上抜けた）
            elif ma5 > ma25 and df['MA5'].iloc[-2] <= df['MA25'].iloc[-2]: score += 50
            # 出来高急増
            if vol_ma5 > 0 and vol_curr > (vol_ma5 * 1.5): score += 20
            
            # 推奨株数計算 (リスクリワードに基づく)
            dist = curr * default_stop_pct # 損切り幅
            rec_shares = math.floor(risk_limit / dist / 100) * 100 if dist > 0 else 0
            
            with st.expander(f"【{s['ticker']}】{s.get('name', '')} | スコア：{score}点", expanded=True):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("価格", f"{curr:,.1f}")
                c2.metric("RSI", f"{rsi:.1f}")
                c3.metric("出来高比", f"{vol_curr/vol_ma5:.1f}倍" if vol_ma5 > 0 else "0")
                
                # 判定バッジ
                if score >= 50:
                    c4.markdown('<div class="status-box status-success">🚀 買い時!!</div>', unsafe_allow_html=True)
                else:
                    c4.markdown('<div class="status-box status-info">💤 監視中</div>', unsafe_allow_html=True)
                
                st.info(f"💡 推奨買付株数: **{rec_shares:,}株** (損切幅: -{dist:,.0f}円/株)")
                
                col_act1, col_act2 = st.columns(2)
                with col_act1:
                    if st.button("保有へ移行", key=f"mov_{s['id']}", use_container_width=True):
                        for p in st.session_state.data["portfolio"]:
                            if p['id'] == s['id']:
                                p['status'] = 'holding'
                                p['price'] = curr
                                p['shares'] = rec_shares
                        sync_github(st.session_state.data, action="save")
                        st.rerun()
                with col_act2:
                    if st.button("削除", key=f"del_w_{s['id']}", use_container_width=True):
                        st.session_state.data["portfolio"] = [x for x in st.session_state.data["portfolio"] if x['id'] != s['id']]
                        sync_github(st.session_state.data, action="save")
                        st.rerun()

if __name__ == "__main__":
    main()