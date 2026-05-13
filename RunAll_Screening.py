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
        result = subprocess.run(cmd, check=True)
        end_time = time.time()
        print(f"\n[成功] {script_name} (実行時間: {end_time - start_time:.2f}秒)")
        return True
    except subprocess.CalledProcessError:
        print(f"\n[エラー] {script_name} の実行中に問題が発生しました。")
        return False

def main():
    # スクリーニング専用のファイル名を指定
    SCREENING_LIST = "tickers_screening.txt"
    
    # スクリーニング時はダッシュボード系を出力しないため、データ関連のみ削除
    clean_dirs = ["data", "calculated_data", "simulation_results"]

    print("スクリーニング環境を初期化しています（古いデータの削除）...")
    for d in clean_dirs:
        if os.path.exists(d):
            try:
                shutil.rmtree(d)
                print(f" - 削除完了: {d}")
            except Exception as e:
                pass

    # スクリーニング用プロセス（チャート生成やダッシュボード生成は省く）
    scripts = [
        ("01_GetValue.py", [SCREENING_LIST]),  # 引数としてスクリーニング用リストを渡す
        ("02_Calculation.py", []),
        ("03_Simulation.py", []),
        # ("04_Screening.py", []) # ★次に作成するスクリーニング評価用スクリプト
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
    print(f"\n スクリーニング基盤構築完了 (実行時間: {total_end_time - total_start_time:.2f}秒)")

if __name__ == "__main__":
    main()