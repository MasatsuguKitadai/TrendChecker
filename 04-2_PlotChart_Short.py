# fileName: 04_PlotChart_Short.py
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# --- 設定 (ショート専用) ---
DATA_DIR = "calculated_data"
RESULT_DIR = "simulation_results_short"       
OUTPUT_CHARTS_DIR = "visualized_charts_short" 
SIM_MONTHS = 6

def visualize_all_analyzed_data_short():
    os.makedirs(OUTPUT_CHARTS_DIR, exist_ok=True)
    
    all_files = [f for f in os.listdir(DATA_DIR) if f.endswith('_analyzed.csv')]
    
    for file_name in all_files:
        ticker = file_name.replace("_analyzed.csv", "")
        df = pd.read_csv(os.path.join(DATA_DIR, file_name), index_col="Date", parse_dates=True)
        
        latest_date = df.index.max()
        sim_start = latest_date - pd.DateOffset(months=SIM_MONTHS)

        trades = pd.DataFrame()
        trade_file = os.path.join(RESULT_DIR, f"{ticker}_trades.csv")
        
        if os.path.exists(trade_file):
            t_df = pd.read_csv(trade_file)
            if not t_df.empty:
                last_short_price = 0
                t_profits, t_rates = [], []
                
                for _, r in t_df.iterrows():
                    action = r['Action']
                    price = r['Price']
                    
                    if action == "SHORT_SELL":
                        last_short_price = price
                        t_profits.append(0.0)
                        t_rates.append(0.0)
                    
                    elif action == "BUY_BACK":
                        roi = (r['Profit'] / last_short_price) * 100 if last_short_price > 0 else 0
                        t_profits.append(r['Profit'])
                        t_rates.append(round(roi, 2))
                    
                    elif action == "HOLDING" and last_short_price != 0:
                        unrealized_profit = last_short_price - price
                        roi = (unrealized_profit / last_short_price) * 100
                        t_profits.append(round(unrealized_profit, 2))
                        t_rates.append(round(roi, 2))
                    
                    else:
                        t_profits.append(0.0)
                        t_rates.append(0.0)
                
                t_df['Trade_Profit'] = t_profits
                t_df['Trade_Rate'] = t_rates
                
                t_df['Cum_Rate'] = round((t_df['Capital'] - 1.0) * 100, 2)
                trades = t_df

        # --- プロット処理 ---
        df_p = df[df.index >= sim_start]
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.15, 0.35],
                            specs=[[{"type": "xy"}], [{"type": "xy"}], [{"type": "table"}]])

        # 1. ローソク足と移動平均線
        fig.add_trace(go.Candlestick(x=df_p.index, open=df_p['Open'], high=df_p['High'], low=df_p['Low'], close=df_p['Close'], name="価格",
                                     increasing_line_color='#dc3545', decreasing_line_color='#28a745'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['MA_Short'], name="MA5", line=dict(color='orange', width=1.2)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['MA_Mid'], name="MA25", line=dict(color='blue', width=1.2)), row=1, col=1)
        
        # 2. MACD (★修正箇所：Signalの参照を MA_Mid から MACD_Signal に変更)
        fig.add_trace(go.Bar(x=df_p.index, y=df_p['MACD_Hist'], name="Hist", marker_color='silver', opacity=0.7), row=2, col=1)
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['MACD'], name="MACD", line=dict(color='black', width=1.2)), row=2, col=1)
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['MACD_Signal'], name="Signal", line=dict(color='red', width=1.2)), row=2, col=1)

        # 3. 売買履歴テーブル
        if not trades.empty:
            for _, r in trades.iterrows():
                lc = "#dc3545" if "BUY" in r['Action'] else ("#28a745" if "SELL" in r['Action'] else "#ffc107")
                fig.add_vline(x=r['Date'], line_width=1, line_dash="dash", line_color=lc, row=1, col=1)

            fig.add_trace(go.Table(
                header=dict(values=["日付", "Action", "価格", "理由", "値幅 (損益率)", "累積率 (リターン)"], 
                            fill_color='#f8f9fa', align='center', font=dict(size=12, color='black')),
                cells=dict(values=[
                    trades['Date'], 
                    trades['Action'], 
                    trades['Price'].map('{:,.1f}'.format), 
                    trades['Reason'],
                    [f"{p:+.1f} ({r:+.2f}%)" if a in ["BUY_BACK", "HOLDING"] else "-" for p, r, a in zip(trades['Trade_Profit'], trades['Trade_Rate'], trades['Action'])],
                    [f"{cr:+.2f}%" for cr in trades['Cum_Rate']]
                ], fill_color='#fff', align=['center', 'center', 'right', 'center', 'right', 'right'],
                   font=dict(size=11))), row=3, col=1)

        fig.update_layout(title=f"{ticker} ショート複利運用レポート (累積率ベース)", template="plotly_white", height=1100, xaxis_rangeslider_visible=False)
        fig.write_html(os.path.join(OUTPUT_CHARTS_DIR, f"chart_{ticker}.html"))
        print(f"◎ {ticker} : ショートチャート生成完了")

if __name__ == "__main__":
    visualize_all_analyzed_data_short()