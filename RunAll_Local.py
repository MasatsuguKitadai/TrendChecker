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
    
    # 引数がある場合はコマンドリストに追加
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
    # ★変更点1：マルチトラック構成のディレクトリ名に修正
    clean_dirs = [
        "simulation_results",        # todays_actions.csv用
        "simulation_results_fixed",  # 固定5%用
        "simulation_results_atr",    # ATR用
        "visualized_charts_fixed",   # 固定5%チャート用
        "visualized_charts_atr"      # ATRチャート用
    ]

    print("日次監視環境を初期化しています（古いデータの削除）...")
    for d in clean_dirs:
        if os.path.exists(d):
            try:
                shutil.rmtree(d)
                print(f" - 削除完了: {d}")
            except Exception as e:
                pass

    # ★変更点2：実行するスクリプトを「固定5%」と「ATR」の並行ルートに修正
    scripts = [
        ("02_Calculation.py", []),
        ("03_Simulation_Fixed.py", []),  # 分岐A
        ("03_Simulation_ATR.py", []),    # 分岐B
        ("04_PlotChart_Fixed.py", []),   # 分岐Aチャート
        ("04_PlotChart_ATR.py", []),     # 分岐Bチャート
        ("05_Summary.py", []),           # 合流・指示書作成
        ("06_CreateDashboard.py", []),   # ダッシュボード生成
    ]

    total_start_time = time.time()
    success_count = 0

    print("\n【日次監視プロセス（マルチ戦略版）】 を開始します...")

    for script, args in scripts:
        if run_script(script, args):
            success_count += 1
        else:
            print(f"\n! 実行を中断します ({script} でエラーが発生しました)")
            break

    total_end_time = time.time()
    print(f"\n 全プロセス終了 (完了数: {success_count}/{len(scripts)}, 実行時間: {total_end_time - total_start_time:.2f}秒)")

if __name__ == "__main__":
    main()