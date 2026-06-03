import os
import pandas as pd
import json
from datetime import datetime

# --- 設定 ---
FIXED_CHART_DIR = "visualized_charts_fixed"
ATR_CHART_DIR = "visualized_charts_atr"

FIXED_RESULT_DIR = "simulation_results_fixed"
ATR_RESULT_DIR = "simulation_results_atr"
ACTION_FILE = "simulation_results/todays_actions.csv"
OUTPUT_FILE = "Dashboard.html"

def generate_dashboard():
    now_str = datetime.now().strftime("%Y/%m/%d")
    
    # 1. アクション指示書（05が生成した共通ファイル）の読み込み
    df_actions = pd.read_csv(ACTION_FILE) if os.path.exists(ACTION_FILE) else pd.DataFrame()
    
    # 2. 各サマリーから利益率を取得する関数
    def get_rate_map(path):
        if os.path.exists(path):
            df = pd.read_csv(path)
            return dict(zip(df['Ticker'].astype(str), df['Profit_Rate_Pct']))
        return {}

    # 固定5%とATRの利益率を別々に取得
    rate_map_fixed = get_rate_map(f"{FIXED_RESULT_DIR}/overall_summary.csv")
    rate_map_atr = get_rate_map(f"{ATR_RESULT_DIR}/overall_summary.csv")

    # 3. 描画用データの統合
    actions_list = []
    if not df_actions.empty:
        for _, row in df_actions.iterrows():
            item = row.to_dict()
            ticker_str = str(row['Ticker'])
            # フロントエンドで切り替えられるよう、両方の利益率を持たせる
            item['ProfitRate_Fixed'] = rate_map_fixed.get(ticker_str, 0.0)
            item['ProfitRate_ATR'] = rate_map_atr.get(ticker_str, 0.0)
            actions_list.append(item)

    actions_json = json.dumps(actions_list)

    # 4. HTML/JSの生成
    html_content = f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Stock Dashboard - Multi Strategy</title>
        <style>
            :root {{ 
                --primary: #007bff; --bg: #ffffff; --sidebar-bg: #f8f9fa; --text: #212529; 
                --border: #dee2e6; --up-color: #dc3545; --down-color: #007bff;
                --not-owned-bg: #f2f2f2; --not-owned-text: #888;
                --header-height: 100px; /* ヘッダーの高さを定義 */
                --nav-height: 50px;    /* ナビゲーションバーの高さを定義 */
                --font-main: 0.95rem;
            }}
            
            body {{ font-family: 'Segoe UI', Roboto, sans-serif; margin: 0; background: var(--bg); color: var(--text); }}
            
            /* 上部固定コンテナ */
            .sticky-header-container {{
                position: sticky;
                top: 0;
                z-index: 1000;
                background: #fff;
            }}

            /* ヘッダーと戦略トグル */
            .dashboard-header {{ padding: 10px; text-align: center; border-bottom: 1px solid var(--border); }}
            .dashboard-header h1 {{ margin: 0 0 10px 0; font-size: 1.2rem; color: #333; }}
            
            .strategy-toggle {{ display: flex; justify-content: center; margin-bottom: 5px; }}
            .strategy-toggle button {{ 
                padding: 6px 24px; cursor: pointer; border: 2px solid var(--primary); 
                background: #fff; color: var(--primary); font-weight: bold; font-size: 0.9rem; transition: 0.2s;
            }}
            .strategy-toggle button.active {{ background: var(--primary); color: #fff; }}
            .strategy-toggle button:first-child {{ border-radius: 20px 0 0 20px; border-right: none; }}
            .strategy-toggle button:last-child {{ border-radius: 0 20px 20px 0; border-left: none; }}

            /* ナビゲーションバー */
            .nav-bar {{ display: flex; background: #fff; border-bottom: 1px solid var(--border); box-shadow: 0 2px 4px rgba(0,0,0,0.05); height: var(--nav-height); }}
            .nav-item {{ flex: 1; text-align: center; line-height: var(--nav-height); cursor: pointer; color: #6c757d; font-weight: 500; border-bottom: 3px solid transparent; }}
            .nav-item.active {{ color: var(--primary); border-bottom-color: var(--primary); background: #f0f7ff; }}
            
            /* メインコンテンツエリアの余白調整 */
            .content-page {{ display: none; min-height: calc(100dvh - 150px); }}
            .content-page.active {{ display: block; }}
            .container {{ width: 98%; max-width: 1000px; padding: 10px 2px; margin: 0 auto; }}
            
            /* テーブルスタイルと固定設定 */
            table {{ width: 100%; border-collapse: separate; border-spacing: 0; background: #fff; }}
            th, td {{ padding: 12px 8px; border-bottom: 1px solid var(--border); font-size: var(--font-main); }}
            
            /* PC環境：ヘッダー(83px) + ナビバー(52px) = 135px の位置に thead(th) を sticky 固定 */
            th {{ 
                background: #f8f9fa; 
                position: sticky; 
                top: calc(var(--header-height) + var(--nav-height)); 
                # z-index: 100; 
                font-size: 0.85em; 
                border-bottom: 2px solid var(--border); 
            }}
            
            /* 非保有・カラーリング */
            .row-not-owned {{ background-color: var(--not-owned-bg) !important; color: var(--not-owned-text) !important; }}
            .row-not-owned b, .row-not-owned small {{ color: var(--not-owned-text) !important; }}

            .gap-up {{ color: var(--up-color); font-weight: bold; }} 
            .gap-down {{ color: var(--down-color); font-weight: bold; }} 
            .rate-plus {{ color: var(--up-color); font-weight: bold; font-size: 0.85em; }}
            .rate-minus {{ color: var(--down-color); font-weight: bold; font-size: 0.85em; }}

            /* アクションバッジ */
            .action-badge {{ padding: 4px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; background: #e9ecef; display: inline-block; white-space: nowrap; transition: 0.3s; }}
            .new-signal {{ background: #fff3cd; color: #856404; border: 1px solid #ffeeba; }}
            .hold-signal {{ background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}

            /* トグルスイッチ（保有） */
            .switch {{ position: relative; display: inline-block; width: 40px; height: 20px; vertical-align: middle; }}
            .switch input {{ opacity: 0; width: 0; height: 0; }}
            .slider {{ position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #ccc; transition: .4s; border-radius: 20px; }}
            .slider:before {{ position: absolute; content: ""; height: 14px; width: 14px; left: 3px; bottom: 3px; background-color: white; transition: .4s; border-radius: 50%; }}
            input:checked + .slider {{ background-color: var(--primary); }}
            input:checked + .slider:before {{ transform: translateX(20px); }}

            /* プルダウン詳細 */
            .detail-row {{ display: none; background-color: #fcfcfc; }}
            .detail-container {{ padding: 12px 5px; display: flex; justify-content: space-around; align-items: center; }}
            .detail-item {{ display: flex; flex-direction: column; align-items: center; flex: 1; }}
            .detail-label {{ font-size: 0.85rem; color: #777; margin-bottom: 4px; }}
            .detail-value {{ font-size: 0.95rem; font-weight: bold; }}

            @media (min-width: 769px) {{
                #page-2.active {{ display: flex; height: calc(100dvh - (var(--header-height) + var(--nav-height))); overflow: hidden; }}
                #sidebar {{ width: 350px; background: var(--sidebar-bg); border-right: 1px solid var(--border); overflow-y: auto; }}
                #chart-area {{ flex: 1; }}
                iframe {{ width: 100%; height: 100%; border: none; }}
                .mobile-only {{ display: none !important; }}
            }}

            @media (max-width: 768px) {{
                .nav-bar {{ display: none !important; }}
                /* スマホ環境：ナビバーが消えるため、ヘッダー(83px)の直下に thead(th) を sticky 固定 */
                th {{ 
                    top: var(--header-height) !important; 
                }} 
                .pc-only {{ display: none !important; }}
                #page-2.active {{ height: calc(100dvh - var(--header-height)); }}
            }}
        </style>
    </head>
    <body>
        <div class="sticky-header-container">
            <header class="dashboard-header">
                <h1>Trend Checker：{now_str}</h1>
                <div class="strategy-toggle">
                    <button id="btn-fixed" onclick="setMode('fixed')">固定</button>
                    <button id="btn-atr" onclick="setMode('atr')" class="active">ATR</button>
                </div>
            </header>
            
            <nav class="nav-bar">
                <div id="nav-1" class="nav-item active" onclick="showPage(1)">保有・アクション</div>
                <div id="nav-2" class="nav-item" onclick="showPage(2)">チャート分析</div>
            </nav>
        </div>

        <main id="page-1" class="content-page active">
            <div class="container">
                <table>
                    <thead>
                        <tr class="pc-only">
                            <th align="center">銘柄</th><th align="center">終値</th>
                            <th align="center">前日比</th><th align="center">アクション<span id="table-mode-label"></span></th>
                            <th align="center">保有</th>
                        </tr>
                        <tr class="mobile-only"><th align="center">銘柄</th><th align="center">アクション</th></tr>
                    </thead>
                    <tbody id="action-body"></tbody>
                </table>
            </div>
        </main>

        <main id="page-2" class="content-page">
            <div id="sidebar"><div id="ticker-list"></div></div>
            <div id="chart-area"><iframe id="frame" name="chart_frame"></iframe></div>
        </main>

        <script>
            const data = {actions_json};
            let currentMode = 'atr'; 
            let currentTicker = null; 

            function getOwnedStatus(ticker) {{ return localStorage.getItem('owned_' + ticker) === 'true'; }}
            
            function toggleOwned(ticker, event) {{
                event.stopPropagation();
                localStorage.setItem('owned_' + ticker, !getOwnedStatus(ticker));
                renderStatus();
            }}

            function toggleDetail(ticker) {{
                if (window.innerWidth > 768) return;
                const el = document.getElementById('detail-' + ticker);
                el.style.display = el.style.display === 'table-row' ? 'none' : 'table-row';
            }}

            function showPage(n) {{
                document.querySelectorAll('.nav-item, .content-page').forEach(el => el.classList.remove('active'));
                document.getElementById('nav-'+n).classList.add('active');
                document.getElementById('page-'+n).classList.add('active');
                if (n===2) renderList();
            }}

            function setMode(mode) {{
                currentMode = mode;
                document.getElementById('btn-fixed').classList.toggle('active', mode === 'fixed');
                document.getElementById('btn-atr').classList.toggle('active', mode === 'atr');
                
                renderStatus();
                renderList();
                if(currentTicker) loadChart(currentTicker); 
            }}

            function loadChart(ticker) {{
                currentTicker = ticker;
                const dir = currentMode === 'fixed' ? '{FIXED_CHART_DIR}' : '{ATR_CHART_DIR}';
                document.getElementById('frame').src = dir + '/chart_' + ticker + '.html';
            }}

            function renderStatus() {{
                const body = document.getElementById('action-body');
                body.innerHTML = '';
                
                data.forEach(r => {{
                    const isOwned = getOwnedStatus(r.Ticker);
                    const rowClass = !isOwned ? 'row-not-owned' : '';
                    const gapClass = r.GapRaw > 0 ? 'gap-up' : (r.GapRaw < 0 ? 'gap-down' : '');
                    
                    const rate = currentMode === 'fixed' ? r.ProfitRate_Fixed : r.ProfitRate_ATR;
                    const actionTxt = currentMode === 'fixed' ? r.Action_Fixed : r.Action_ATR;
                    const actionType = currentMode === 'fixed' ? r.Type_Fixed : r.Type_ATR;

                    const rateClass = rate > 0 ? 'rate-plus' : (rate < 0 ? 'rate-minus' : '');
                    const rateText = `<span class="${{rateClass}}"> (${{rate > 0 ? '+':''}}${{rate}}%)</span>`;
                    
                    let bCls = 'action-badge';
                    if (actionType.startsWith('NEW')) bCls += ' new-signal';
                    else if (actionTxt.includes('保持') || actionTxt.includes('トレイル') || actionTxt.includes('ストップ')) bCls += ' hold-signal';

                    const sw = `<label class="switch"><input type="checkbox" ${{isOwned ? 'checked' : ''}} onchange="toggleOwned('${{r.Ticker}}', event)"><span class="slider"></span></label>`;

                    body.innerHTML += `
                        <tr class="${{rowClass}}" onclick="toggleDetail('${{r.Ticker}}')">
                            <td align="left"><b>${{r.Ticker}}</b>${{rateText}}<br><small style="color:#666;">${{r.Name}}</small></td>
                            <td align="center" class="pc-only" style="font-weight:600;">${{Math.floor(r.Close).toLocaleString()}}</td>
                            <td align="center" class="pc-only ${{gapClass}}">${{r.GapText}}</td>
                            <td align="center"><span class="${{bCls}}">${{actionTxt}}</span></td>
                            <td align="center" class="pc-only">${{sw}}</td>
                        </tr>
                        <tr id="detail-${{r.Ticker}}" class="detail-row ${{rowClass}}">
                            <td colspan="5">
                                <div class="detail-container">
                                    <div class="detail-item"><span class="detail-label">終値</span><span class="detail-value">${{Math.floor(r.Close).toLocaleString()}}</span></div>
                                    <div class="detail-item"><span class="detail-label">前日比</span><span class="detail-value ${{gapClass}}">${{r.GapText}}</span></div>
                                    <div class="detail-item"><span class="detail-label">保有</span>${{sw}}</div>
                                </div>
                            </td>
                        </tr>
                    `;
                }});
            }}

            function renderList() {{
                const list = document.getElementById('ticker-list');
                const label = currentMode === 'fixed' ? 'リスト' : 'リスト';
                list.innerHTML = `<div style="padding:15px; font-weight:bold; border-bottom:1px solid #ddd; font-size: 0.9rem;">${{label}}</div>`;
                
                data.forEach(r => {{
                    const rate = currentMode === 'fixed' ? r.ProfitRate_Fixed : r.ProfitRate_ATR;
                    const rateClass = rate > 0 ? 'rate-plus' : (rate < 0 ? 'rate-minus' : '');
                    const div = document.createElement('div');
                    div.style.cssText = 'padding:15px; border-bottom:1px solid #eee; cursor:pointer; font-size: 0.95rem; transition: background 0.2s;';
                    div.innerHTML = `<b>${{r.Ticker}}</b> <span class="${{rateClass}}">(${{rate}}%)</span><br><small style="color:#666;">${{r.Name}}</small>`;
                    
                    div.onmouseover = () => div.style.background = '#f1f8ff';
                    div.onmouseout = () => div.style.background = 'transparent';
                    div.onclick = () => loadChart(r.Ticker);
                    
                    list.appendChild(div);
                }});
            }}
            
            renderStatus(); 
        </script>
    </body>
    </html>
    """
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f: 
        f.write(html_content)
    print(f"◎ Dashboard.html を更新しました。（固定 / ATR 切り替え対応）")

if __name__ == "__main__": 
    generate_dashboard()