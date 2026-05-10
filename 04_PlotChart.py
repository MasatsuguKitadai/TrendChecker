import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

DATA_DIR, RESULT_DIR, OUTPUT_CHARTS_DIR = "calculated_data", "simulation_results", "visualized_charts"
SIM_MONTHS = 6

def visualize_all_analyzed_data():
    os.makedirs(OUTPUT_CHARTS_DIR, exist_ok=True)
    for file_name in [f for f in os.listdir(DATA_DIR) if f.endswith('_analyzed.csv')]:
        ticker = file_name.replace("_analyzed.csv", "")
        df = pd.read_csv(os.path.join(DATA_DIR, file_name), index_col="Date", parse_dates=True)
        
        latest_date = df.index.max()
        sim_start = latest_date - pd.DateOffset(months=SIM_MONTHS)
        base_price = df.loc[sim_start:].iloc[0]['Close'] if sim_start in df.index else df['Close'].iloc[0]

        trades = pd.DataFrame()
        if os.path.exists(os.path.join(RESULT_DIR, f"{ticker}_trades.csv")):
            t_df = pd.read_csv(os.path.join(RESULT_DIR, f"{ticker}_trades.csv"))
            if not t_df.empty:
                t_df['Cumulative'] = t_df['Profit'].cumsum()
                last_buy = 0
                t_rates, c_rates = [], []
                for _, r in t_df.iterrows():
                    if r['Action'] == "BUY": last_buy = r['Price']
                    # ★ SELLだけでなく、HOLDING時も買値と比較して損益率を出す
                    if r['Action'] in ["SELL", "HOLDING"] and last_buy != 0:
                        t_rates.append(round((r['Profit'] / last_buy) * 100, 2))
                    else:
                        t_rates.append(0.0)
                    c_rates.append(round((r['Cumulative'] / base_price) * 100, 2))
                t_df['Trade_Rate'], t_df['Cum_Rate'] = t_rates, c_rates
                trades = t_df

        df_p = df[df.index >= sim_start]
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.15, 0.35],
                            specs=[[{"type": "xy"}], [{"type": "xy"}], [{"type": "table"}]])

        fig.add_trace(go.Candlestick(x=df_p.index, open=df_p['Open'], high=df_p['High'], low=df_p['Low'], close=df_p['Close'], name="価格",
                                     increasing_line_color='#dc3545', decreasing_line_color='#28a745'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['MA_Short'], name="MA5", line=dict(color='orange', width=1.2)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['MA_Mid'], name="MA25", line=dict(color='blue', width=1.2)), row=1, col=1)
        fig.add_trace(go.Bar(x=df_p.index, y=df_p['MACD_Hist'], name="Hist", marker_color='silver', opacity=0.7), row=2, col=1)
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['MACD'], name="MACD", line=dict(color='black', width=1.2)), row=2, col=1)
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['MACD_Signal'], name="Signal", line=dict(color='red', width=1.2)), row=2, col=1)

        if not trades.empty:
            for _, r in trades.iterrows():
                lc = "#dc3545" if "BUY" in r['Action'] else ("#28a745" if "SELL" in r['Action'] else "orange")
                fig.add_vline(x=r['Date'], line_width=1, line_dash="dash", line_color=lc, row=1, col=1)

            fig.add_trace(go.Table(
                header=dict(values=["日付", "Action", "価格", "理由", "損益 (率)", "累積 (率)"], fill_color='#f8f9fa', align='center'),
                cells=dict(values=[
                    trades['Date'], trades['Action'], trades['Price'].map('{:,.1f}'.format), trades['Reason'],
                    # ★ HOLDING行でも含み益を表示
                    [f"{p:+,.1f} ({r:+.1f}%)" if a in ["SELL", "HOLDING"] else "-" for p, r, a in zip(trades['Profit'], trades['Trade_Rate'], trades['Action'])],
                    [f"{c:+,.1f} ({cr:+.1f}%)" for c, cr in zip(trades['Cumulative'], trades['Cum_Rate'])]
                ], fill_color='#fff', align=['center', 'center', 'right', 'center', 'right', 'right'])), row=3, col=1)

        fig.update_layout(title=f"{ticker} 解析レポート", template="plotly_white", height=1100, xaxis_rangeslider_visible=False)
        fig.write_html(os.path.join(OUTPUT_CHARTS_DIR, f"chart_{ticker}.html"))

if __name__ == "__main__":
    visualize_all_analyzed_data()