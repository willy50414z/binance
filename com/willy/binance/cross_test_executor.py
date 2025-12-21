import itertools
from concurrent.futures import ProcessPoolExecutor

import pandas as pd

from com.willy.binance.enums.binance_product import BinanceProduct
from com.willy.binance.service import trade_svc
from com.willy.binance.strategy.moving_average_strategy import MovingAverageStrategy
from com.willy.binance.util import type_util


def run_experiment(strategy):
    """
    單一實驗執行點：這是給多執行緒呼叫的入口
    config 格式: {'use_rsi': True, 'use_adx': False, ...}
    """
    test_id = f"EXP_{sum(strategy.cross_test_config.values())}_" + "_".join(
        [k for k, v in strategy.cross_test_config.items() if v])

    # 執行回測
    strategy.run_backtest()

    # 提取結果分析 (從 trade_svc 的總結獲取)
    summary = trade_svc.get_backtest_summary(strategy.trade_detail)

    # 併入當前的配置資訊，方便後續分析
    summary.update(strategy.cross_test_config)
    summary['test_id'] = test_id
    return summary


if __name__ == '__main__':
    strategy = MovingAverageStrategy("ma_with_ma25_0101_1130_no_stop_profit_germini_1",
                                     # type_util.str_to_datetime("2025-11-01T00:00:00Z"),
                                     type_util.str_to_datetime("2025-11-01T00:00:00Z"),
                                     type_util.str_to_datetime("2025-12-21T00:00:00Z"), 6000
                                     , BinanceProduct.BTCUSDT, 20, {})

    # 這裡初始化你的策略，並傳入 config
    switches = list(strategy.strategy_idx_switches)

    # 2. 產生所有 True/False 的排列組合 (2^n)
    combinations = list(itertools.product([True, False], repeat=len(switches)))

    # 3. 組合成字典，這裡 Key 就是 Enum 成員
    all_configs = [dict(zip(switches, combo)) for combo in combinations]

    print(f"🚀 開始交叉測試，共 {len(all_configs)} 組配置...")

    # 3. 使用 ProcessPoolExecutor 進行多執行緒運算
    # 注意：量化回測通常是 CPU 密集，ProcessPool 比 ThreadPool 有效
    with ProcessPoolExecutor(max_workers=None) as executor:  # None 自動抓 CPU 核心數
        results = list(executor.map(run_experiment, all_configs))

    # 4. 結果分析與排名
    analysis_df = pd.DataFrame(results)

    # 依照獲利因子或總報酬排序
    analysis_df = analysis_df.sort_values(by='總報酬率 (%)', ascending=False)

    # 5. 輸出前五名最佳組合
    print("\n🏆 最佳策略組合排名：")
    print(analysis_df[['test_id', '總報酬率 (%)', '勝率 (%)', '獲利因子']].head(5))

    # 存成 Excel 方便你細看
    analysis_df.to_csv("backtest_optimization_results.csv", index=False)
