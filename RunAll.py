import subprocess
import sys
import time
import os
import shutil

def run_script(script_name):
    """
    指定されたPythonスクリプトを実行する補助関数
    """
    print(f"\n{'='*50}")
    print(f" 実行中: {script_name}")
    print(f"{'='*50}")
    
    start_time = time.time()
    
    try:
        # 現在実行中のPythonインタープリタを使用してスクリプトを実行[cite: 11]
        result = subprocess.run([sys.executable, script_name], check=True)
        end_time = time.time()
        print(f"\n[成功] {script_name} (実行時間: {end_time - start_time:.2f}秒)")
        return True
    except subprocess.CalledProcessError:
        print(f"\n[エラー] {script_name} の実行中に問題が発生しました。")
        return False

def main():
    # 削除対象のディレクトリリスト
    clean_dirs = [
        "data",                      # 取得したデータ
        "calculated_data",           # 指標計算データ
        "simulation_results",        # 買いトレード結果
        "simulation_results_short",  # 空売りトレード結果
        "visualized_charts",         # 買いチャート（HTML）
        "visualized_charts_short"    # 空売りチャート（HTML）
    ]

    print("解析環境を初期化しています（古いデータの削除）...")
    for d in clean_dirs:
        if os.path.exists(d):
            try:
                shutil.rmtree(d)
                print(f" - 削除完了: {d}")
            except Exception as e:
                print(f" - {d} の削除中にエラーが発生しました: {e}")

    # 実行するスクリプトのリスト（順番が重要です）[cite: 11]
    scripts = [
        "01_GetValue.py",         # 1. データ収集[cite: 3, 11]
        "02_Calculation.py",      # 2. 指標計算[cite: 4, 11]
        "03_Simulation.py",       # 3. 買いシミュレーション[cite: 9, 11]
        "04_Check.py",            # 4. 買い可視化[cite: 6, 11]
        # "05_Simulation_Short.py", # 5. 空売りシミュレーション[cite: 10, 11]
        # "06_Check_Short.py",      # 6. 空売り可視化[cite: 4, 11]
        "07_Results.py",          # 7. 明日のアクション指示[cite: 8, 11]
        "08_CreateDashboard.py"   # 8. ダッシュボード生成[cite: 5, 11]
        "09_SendEmail.py"
    ]

    total_start_time = time.time()
    success_count = 0

    print("\n株価分析システム 一括実行プロセスを開始します...")

    for script in scripts:
        if run_script(script):
            success_count += 1
        else:
            print(f"\n! 実行を中断します ({script} でエラーが発生しました)[cite: 11]")
            break

    total_end_time = time.time()
    
    print(f"\n{'='*50}")
    print(f" 全プロセス終了")
    print(f" 完了数: {success_count}/{len(scripts)}")
    print(f" 総実行時間: {total_end_time - total_start_time:.2f}秒")
    
    if success_count == len(scripts):
        print("\n すべての工程が正常に完了しました！")
        print(" Dashboard.html を開いて結果を確認してください。[cite: 11]")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()