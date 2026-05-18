import subprocess
import sys
import time
import os
import shutil

def run_script(script_name, args=None):
    print(f"\n{'='*50}")
    print(f" 実行中: {script_name} " + (f"[{args[0]}]" if args else ""))
    print(f"{'='*50}")
    
    start_time = time.time()
    
    cmd = [sys.executable, script_name]
    if args:
        cmd.extend(args)
        
    try:
        subprocess.run(cmd, check=True)
        end_time = time.time()
        print(f"\n[成功] {script_name} (実行時間: {end_time - start_time:.2f}秒)")
        return True
    except subprocess.CalledProcessError:
        print(f"\n[エラー] {script_name} の実行中に問題が発生しました。")
        return False

def main():
    # 読み込むスクリーニング用の銘柄リスト
    SCREENING_LIST = "tickers_screening.txt"
    
    clean_dirs = ["data", "calculated_data", "simulation_results"]

    print("スクリーニング環境を初期化しています（古いデータの削除）...")
    for d in clean_dirs:
        if os.path.exists(d):
            try:
                shutil.rmtree(d)
                print(f" - 削除完了: {d}")
            except Exception:
                pass

    # 実行するプロセス（チャート可視化などは除外）
    scripts = [
        ("01_GetValue.py", [SCREENING_LIST]),  # 引数でリストを切り替え
        ("02_Calculation.py", []),             # 通常の指標計算
        ("03_Simulation.py", []),              # 通常のシミュレーション
        ("08_Screening.py", [])                # ★今回作成した抽出スクリプト
    ]

    total_start_time = time.time()
    success_count = 0

    print(f"\n【新規銘柄発掘プロセス】 (対象: {SCREENING_LIST}) を開始します...")

    for script, args in scripts:
        if run_script(script, args):
            success_count += 1
        else:
            print(f"\n! 実行を中断します ({script} でエラーが発生しました)")
            break

    total_end_time = time.time()
    print(f"\n スクリーニングプロセス完了 (実行時間: {total_end_time - total_start_time:.2f}秒)")
    print(" 出力された screened_tickers.txt の内容を tickers.txt にコピーして日次監視に追加できます。")

if __name__ == "__main__":
    main()