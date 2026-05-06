import pandas as pd
import os

# --- 設定 ---
INPUT_DIR = "data"
OUTPUT_DIR = "calculated_data"

def calculate_indicators_v2_auto():
    # 出力用フォルダの作成
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 1. dataディレクトリ内の全CSVファイルを取得して銘柄リストを作成
    all_files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.csv')]
    
    if not all_files:
        print(f"× {INPUT_DIR} フォルダにCSVファイルが見つかりません。")
        return

    print(f"--- 全 {len(all_files)} 銘柄の指標計算開始 ---")
    
    for file_name in all_files:
        ticker = file_name.replace(".csv", "")
        file_path = os.path.join(INPUT_DIR, file_name)
            
        try:
            # 2. データの読み込み (Open, High, Low, Close が含まれている)[cite: 4]
            df = pd.read_csv(file_path, index_col="Date", parse_dates=True)
            
            # 3. 移動平均線 (MA) の計算[cite: 4]
            df['MA_Short'] = df['Close'].rolling(window=5).mean()
            df['MA_Mid'] = df['Close'].rolling(window=25).mean()
            df['MA_Long'] = df['Close'].rolling(window=75).mean()
            
            # 4. MACD の計算[cite: 4]
            ema12 = df['Close'].ewm(span=12, adjust=False).mean()
            ema26 = df['Close'].ewm(span=26, adjust=False).mean()
            df['MACD'] = ema12 - ema26
            df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
            df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
            
            # 【変更点1】全数値を小数点第1位までに丸める
            df = df.round(1)
            
            # 【変更点2】Index(Date列)の時刻・タイムゾーン情報を削除し「YYYY-MM-DD」形式にする
            df.index = df.index.strftime('%Y-%m-%d')
            
            # 5. CSVとして出力
            output_path = f"{OUTPUT_DIR}/{ticker}_analyzed.csv"
            df.to_csv(output_path)
            print(f"◎ {ticker}: 指標計算完了")
            
        except Exception as e:
            print(f"! {ticker} 計算エラー: {e}")

if __name__ == "__main__":
    calculate_indicators_v2_auto()