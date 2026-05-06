import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# --- 設定 ---
DATA_DIR = "calculated_data"
RESULT_DIR = "simulation_results_short"   
OUTPUT_CHARTS_DIR = "visualized_charts_short" 

def visualize_short_analyzed_data():
    os.makedirs(OUTPUT_CHARTS_DIR, exist_ok=True)
    all_files = [f for f in os.listdir(DATA_DIR) if f.endswith('_analyzed.csv')]
    
    for file_name in all_files:
        ticker = file_name.replace("_analyzed.csv", "")
        data_path = os.path.join(DATA_DIR, file_name)
        trade_path = os.path.join(RESULT_DIR, f"{ticker}_trades.csv")
        df = pd.read_csv(data_path, index_col="Date", parse_dates=True)
        
        trades = pd.DataFrame(columns=["Date", "Action", "Price", "Reason", "Profit"])
        if os.path.exists(trade_path):
            try:
                temp_trades = pd.read_csv(trade_path, parse_dates=["Date"])
                if not temp_trades.empty: trades = temp_trades
            except pd.errors.EmptyDataError: pass

        latest_date = df.index.max()
        df = df[df.index >= (latest_date - pd.DateOffset(months=6))]

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])

        # ローソク足：SBI配色設定
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="価格",
            increasing_line_color='#dc3545', decreasing_line_color='#28a745'
        ), row=1, col=1)

        fig.add_trace(go.Scatter(x=df.index, y=df['MA_Short'], name="MA5", line=dict(color='orange', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA_Mid'], name="MA25", line=dict(color='blue', width=1)), row=1, col=1)

        fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], name="Hist", marker_color='silver'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], name="MACD", line=dict(color='black', width=1)), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD_Signal'], name="Signal", line=dict(color='red', width=1)), row=2, col=1)

        if not trades.empty:
            for _, row in trades.iterrows():
                # 【修正箇所】保持日(HOLDING)はピンク、買戻し(BUY系)は赤、新規売(SHORT系)は緑
                if row['Action'] == "HOLDING":
                    line_color = "black"
                    line_dash = "dash"
                elif row['Action'] in ["BUY", "BUY_SIGNAL", "BUYBACK"]:
                    line_color = "#dc3545"
                    line_dash = "dash"
                else:
                    line_color = "#28a745"
                    line_dash = "dash"
                
                # 垂直線を引く
                fig.add_vline(x=row['Date'], line_width=1.5, line_dash=line_dash, line_color=line_color, row=1, col=1)

        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
        fig.update_layout(title=f"{ticker} ショート解析 (直近6ヶ月)", template="plotly_white", height=800, xaxis_rangeslider_visible=False)

        fig.write_html(os.path.join(OUTPUT_CHARTS_DIR, f"chart_short_{ticker}.html"))

if __name__ == "__main__":
    visualize_short_analyzed_data()