import itertools
import os
from concurrent.futures import ProcessPoolExecutor
from typing import Type

import pandas as pd

from com.willy.binance.config import const
from com.willy.binance.strategy.ma_7_25_break_strategy import Ma725BreakStrategy


def evaluate_performance(analysis_df, initial_capital):
    """計算更完整的策略 KPI，包含風險指標"""
    # 確保資料是照時間排序的
    analysis_df = analysis_df.sort_index()

    # 找出所有交易結算的點
    trades = analysis_df[analysis_df['profit'].notnull()].copy()

    if trades.empty:
        return {'total_return_pct': 0, 'win_rate': 0, 'profit_factor': 0,
                'max_drawdown': 0, 'sharpe_ratio': 0, 'trade_count': 0}

    # --- 1. 收益指標 ---
    final_balance = analysis_df['acct_balance'].ffill().iloc[-1]
    total_return_pct = ((final_balance - initial_capital) / initial_capital) * 100

    # --- 2. 勝率與獲利因子 ---
    win_trades = trades[trades['profit'] > 0]
    trade_count = len(trades)
    win_rate = (len(win_trades) / trade_count) * 100 if trade_count > 0 else 0

    gross_profit = trades[trades['profit'] > 0]['profit'].sum()
    gross_loss = abs(trades[trades['profit'] < 0]['profit'].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

    # --- 3. 最大回撤 (Max Drawdown) ---
    # 計算帳戶餘額的歷史最高點，進而算出從最高點掉下來的百分比
    balance_curve = analysis_df['acct_balance'].ffill()
    historical_max = balance_curve.expanding().max()
    drawdowns = (balance_curve - historical_max) / historical_max
    max_drawdown = drawdowns.min() * 100  # 這裡是負值，例如 -15.5 代表回撤 15.5%

    # --- 4. 夏普比率 (Sharpe Ratio) 簡化版 ---
    # 衡量每承受一單位風險能換到的超額回報
    returns = balance_curve.pct_change().dropna()
    if len(returns) > 1 and returns.std() != 0:
        # 這裡假設無風險利率為 0，並將日波動轉為年化 (以加密貨幣 24/7 計算)
        sharpe = (returns.mean() / returns.std()) * (365 ** 0.5)
    else:
        sharpe = 0

    return {
        'total_return_pct': round(total_return_pct, 2),
        'max_drawdown': round(max_drawdown, 2),
        'sharpe_ratio': round(sharpe, 2),
        'win_rate': round(win_rate, 2),
        'profit_factor': round(profit_factor, 2),
        'trade_count': trade_count,
        'avg_profit': round(trades['profit'].mean(), 2)
    }


def run_experiment_wrapper(task_args):
    """
    接收封裝好的參數：(strategy_type, strategy_args, config)
    """
    strat_type, strat_args, config = task_args

    # 實例化
    curr_strategy = strat_type(*strat_args)
    curr_strategy.cross_test_config = config
    label = " + ".join([k.name for k, v in config.items() if v]) or "Base"
    curr_strategy.test_name = f"{curr_strategy.test_name}_{label}"

    # 執行回測
    analyze_df = curr_strategy.run_backtest()
    df_for_analysis = curr_strategy.build_analysis_df(analyze_df)

    # 計算統計
    stats = evaluate_performance(df_for_analysis, curr_strategy.initial_capital)

    # 加上標籤
    stats['test_id'] = label
    for k, v in config.items():
        stats[k.name] = v

    return stats


def start(strategy_type: Type[Ma725BreakStrategy], strategy_args: tuple):
    # 取得 Enum 類別
    temp_strat = strategy_type(*strategy_args)
    switches = list(temp_strat.strategy_idx_switches)

    # 產生所有組合
    combinations = list(itertools.product([True, False], repeat=len(switches)))
    all_configs = [dict(zip(switches, combo)) for combo in combinations]

    print(f"🚀 啟動多核交叉回測 | 核心目標: {strategy_type.__name__}")
    print(f"組合數量: {len(all_configs)}")

    # 打包任務參數供 map 使用
    tasks = [(strategy_type, strategy_args, conf) for conf in all_configs]

    with ProcessPoolExecutor() as executor:
        results = list(executor.map(run_experiment_wrapper, tasks))

    # 排名與輸出
    report_df = pd.DataFrame(results).sort_values(by='total_return_pct', ascending=False)

    print("\n🏆 全能回測優化排行榜 (前 10 名):")
    # 加入 max_drawdown 和 sharpe_ratio
    display_cols = ['test_id', 'total_return_pct', 'max_drawdown', 'sharpe_ratio', 'profit_factor', 'trade_count']
    print(report_df[display_cols].head(10))

    strategy_optimization_report_dir = f"{const.PROJECT_DIR}/report"
    os.makedirs(strategy_optimization_report_dir, exist_ok=True)
    report_df.to_csv(f"{strategy_optimization_report_dir}/strategy_optimization_report.csv", index=False)
    print(f"\n✅ 結果已匯出至 strategy_optimization_report.csv")
