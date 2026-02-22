# Freqtrade Backtesting Result

## Run

- Strategy: `AMRS3_7Strategy`
- Timerange: `20240101-20261231`
- Stem: `backtest-result-2026-02-22_23-51-51`
- Backtest result:
  `E:\code\binance\com\willy\binance\freqtrade\user_data\backtest_results\backtest-result-2026-02-22_23-51-51\backtest-result-2026-02-22_23-51-51.json`
- Signals:
  `E:\code\binance\com\willy\binance\freqtrade\user_data\backtest_results\backtest-result-2026-02-22_23-51-51\backtest-result-2026-02-22_23-51-51_signals.pkl`
- Rejected:
  `E:\code\binance\com\willy\binance\freqtrade\user_data\backtest_results\backtest-result-2026-02-22_23-51-51\backtest-result-2026-02-22_23-51-51_rejected.pkl`
- Market Change:
  `E:\code\binance\com\willy\binance\freqtrade\user_data\backtest_results\backtest-result-2026-02-22_23-51-51\backtest-result-2026-02-22_23-51-51_market_change.feather`
- Meta:
  `E:\code\binance\com\willy\binance\freqtrade\user_data\backtest_results\backtest-result-2026-02-22_23-51-51.meta.json`
- Zip: `E:\code\binance\com\willy\binance\freqtrade\user_data\backtest_results\backtest-result-2026-02-22_23-51-51.zip`
- Strategy file:
  `E:\code\binance\com\willy\binance\freqtrade\strategy\AMRS(ATR-Driven Mean Reversion Short\AMRS3_7Strategy.py`

## Summary

| Metric                | Value    |
|-----------------------|----------|
| Total Trades          | 225      |
| Win Rate              | 60.89%   |
| Profit Total %        | -22.03%  |
| Profit Abs            | -1321.80 |
| Profit Factor         | 0.82     |
| Sharpe                | -0.52    |
| Sortino               | -2.81    |
| Calmar                | -1.81    |
| Max Drawdown %        | 29.85%   |
| Avg Duration (s)      | 219720.0 |
| Backtest Days         | 780      |
| CAGR %                | -10.99%  |
| Trade Profit Max %    | 5.92%    |
| Trade Profit Min %    | -5.15%   |
| Trade Profit Median % | 1.79%    |

## Trades (交易紀錄)

| 時間                        | 買賣   |    數量 |          價格 | 交易原因                                            |
|---------------------------|------|------:|------------:|-------------------------------------------------|
| 2024-01-03 08:30:00+00:00 | SELL | 0.043 |     45190.3 | [BTC/USDT:USDT] enter                           |
| 2024-01-03 11:45:00+00:00 | BUY  | 0.043 |     44152.5 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.20%) |
| 2024-01-03 13:30:00+00:00 | SELL | 0.046 |       42478 | [BTC/USDT:USDT] enter                           |
| 2024-01-04 20:30:00+00:00 | BUY  | 0.046 |     44601.9 | [BTC/USDT:USDT] exit:stop_loss (-5.06%)         |
| 2024-01-05 16:00:00+00:00 | SELL | 0.045 |     43495.1 | [BTC/USDT:USDT] enter                           |
| 2024-01-08 17:45:00+00:00 | BUY  | 0.045 |   45669.855 | [BTC/USDT:USDT] exit:stop_loss (-5.00%)         |
| 2024-01-09 22:45:00+00:00 | SELL | 0.041 |     46010.7 | [BTC/USDT:USDT] enter                           |
| 2024-01-10 12:45:00+00:00 | BUY  | 0.041 |   44999.213 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.12%) |
| 2024-01-10 13:15:00+00:00 | SELL | 0.043 |     45075.7 | [BTC/USDT:USDT] enter                           |
| 2024-01-10 23:00:00+00:00 | BUY  | 0.043 |   47329.485 | [BTC/USDT:USDT] exit:stop_loss (-5.09%)         |
| 2024-01-12 00:15:00+00:00 | SELL | 0.041 |     46264.8 | [BTC/USDT:USDT] enter                           |
| 2024-01-12 16:30:00+00:00 | BUY  | 0.041 |  44032.6285 | [BTC/USDT:USDT] exit:trailing_stop_loss (4.75%) |
| 2024-01-12 17:45:00+00:00 | SELL | 0.044 |     43605.1 | [BTC/USDT:USDT] enter                           |
| 2024-01-12 22:00:00+00:00 | BUY  | 0.044 |     42325.5 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.84%) |
| 2024-01-13 00:30:00+00:00 | SELL | 0.045 |     42791.1 | [BTC/USDT:USDT] enter                           |
| 2024-01-18 20:45:00+00:00 | BUY  | 0.045 |   41283.704 | [BTC/USDT:USDT] exit:trailing_stop_loss (3.60%) |
| 2024-01-18 21:15:00+00:00 | SELL | 0.048 |     40941.3 | [BTC/USDT:USDT] enter                           |
| 2024-01-22 20:00:00+00:00 | BUY  | 0.048 |    39993.03 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.34%) |
| 2024-01-22 20:15:00+00:00 | SELL | 0.049 |     39967.8 | [BTC/USDT:USDT] enter                           |
| 2024-01-23 15:30:00+00:00 | BUY  | 0.049 |   39123.175 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.04%) |
| 2024-01-25 16:45:00+00:00 | SELL |  0.05 |     39815.5 | [BTC/USDT:USDT] enter                           |
| 2024-01-26 16:30:00+00:00 | BUY  |  0.05 |   41806.275 | [BTC/USDT:USDT] exit:stop_loss (-5.07%)         |
| 2024-01-28 22:15:00+00:00 | SELL | 0.047 |     41898.1 | [BTC/USDT:USDT] enter                           |
| 2024-02-07 20:15:00+00:00 | BUY  | 0.047 |   43993.005 | [BTC/USDT:USDT] exit:stop_loss (-4.83%)         |
| 2024-02-12 10:15:00+00:00 | SELL |  0.04 |     47971.9 | [BTC/USDT:USDT] enter                           |
| 2024-02-12 17:30:00+00:00 | BUY  |  0.04 |   50370.495 | [BTC/USDT:USDT] exit:stop_loss (-5.09%)         |
| 2024-02-13 16:00:00+00:00 | SELL | 0.039 |     48753.2 | [BTC/USDT:USDT] enter                           |
| 2024-02-14 09:00:00+00:00 | BUY  | 0.039 |    51190.86 | [BTC/USDT:USDT] exit:stop_loss (-5.07%)         |
| 2024-02-15 21:15:00+00:00 | SELL | 0.036 |     51790.4 | [BTC/USDT:USDT] enter                           |
| 2024-02-26 19:15:00+00:00 | BUY  | 0.036 |    54379.92 | [BTC/USDT:USDT] exit:stop_loss (-4.64%)         |
| 2024-03-01 02:45:00+00:00 | SELL |  0.03 |     61117.5 | [BTC/USDT:USDT] enter                           |
| 2024-03-04 00:30:00+00:00 | BUY  |  0.03 |   64173.375 | [BTC/USDT:USDT] exit:stop_loss (-4.65%)         |
| 2024-03-05 17:45:00+00:00 | SELL | 0.028 |     65072.5 | [BTC/USDT:USDT] enter                           |
| 2024-03-05 19:15:00+00:00 | BUY  | 0.028 |  63477.7955 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.35%) |
| 2024-03-05 20:15:00+00:00 | SELL | 0.029 |     63107.8 | [BTC/USDT:USDT] enter                           |
| 2024-03-06 05:30:00+00:00 | BUY  | 0.029 |    66263.19 | [BTC/USDT:USDT] exit:stop_loss (-5.07%)         |
| 2024-03-07 07:00:00+00:00 | SELL | 0.027 |     65931.6 | [BTC/USDT:USDT] enter                           |
| 2024-03-08 15:15:00+00:00 | BUY  | 0.027 |    69228.18 | [BTC/USDT:USDT] exit:stop_loss (-4.93%)         |
| 2024-03-12 16:00:00+00:00 | SELL | 0.024 |     71779.2 | [BTC/USDT:USDT] enter                           |
| 2024-03-12 17:15:00+00:00 | BUY  | 0.024 |       69629 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.95%) |
| 2024-03-12 17:45:00+00:00 | SELL | 0.025 |     70217.2 | [BTC/USDT:USDT] enter                           |
| 2024-03-13 08:15:00+00:00 | BUY  | 0.025 |    73728.06 | [BTC/USDT:USDT] exit:stop_loss (-5.00%)         |
| 2024-03-14 14:30:00+00:00 | SELL | 0.024 |     72265.7 | [BTC/USDT:USDT] enter                           |
| 2024-03-14 16:30:00+00:00 | BUY  | 0.024 |     70948.5 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.76%) |
| 2024-03-14 16:45:00+00:00 | SELL | 0.025 |     70827.8 | [BTC/USDT:USDT] enter                           |
| 2024-03-14 19:30:00+00:00 | BUY  | 0.025 |       69629 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.59%) |
| 2024-03-15 04:15:00+00:00 | SELL | 0.026 |     68531.2 | [BTC/USDT:USDT] enter                           |
| 2024-03-15 09:00:00+00:00 | BUY  | 0.026 |     66563.7 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.79%) |
| 2024-03-15 11:15:00+00:00 | SELL | 0.026 |     67316.8 | [BTC/USDT:USDT] enter                           |
| 2024-03-15 19:00:00+00:00 | BUY  | 0.026 |    70682.64 | [BTC/USDT:USDT] exit:stop_loss (-5.09%)         |
| 2024-03-15 21:15:00+00:00 | SELL | 0.025 |     68204.4 | [BTC/USDT:USDT] enter                           |
| 2024-03-16 22:30:00+00:00 | BUY  | 0.025 |     66827.6 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.98%) |
| 2024-03-16 23:00:00+00:00 | SELL | 0.026 |     66398.6 | [BTC/USDT:USDT] enter                           |
| 2024-03-19 07:00:00+00:00 | BUY  | 0.026 |    64909.25 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.31%) |
| 2024-03-19 08:15:00+00:00 | SELL | 0.027 |     64438.7 | [BTC/USDT:USDT] enter                           |
| 2024-03-19 15:30:00+00:00 | BUY  | 0.027 |  63348.2815 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.59%) |
| 2024-03-20 00:15:00+00:00 | SELL | 0.029 |     62174.4 | [BTC/USDT:USDT] enter                           |
| 2024-03-20 18:45:00+00:00 | BUY  | 0.029 |    65283.12 | [BTC/USDT:USDT] exit:stop_loss (-5.08%)         |
| 2024-03-21 20:00:00+00:00 | SELL | 0.027 |     65274.3 | [BTC/USDT:USDT] enter                           |
| 2024-03-22 15:00:00+00:00 | BUY  | 0.027 |  63553.7175 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.57%) |
| 2024-03-22 16:30:00+00:00 | SELL | 0.028 |     63554.1 | [BTC/USDT:USDT] enter                           |
| 2024-03-24 21:45:00+00:00 | BUY  | 0.028 |   66731.805 | [BTC/USDT:USDT] exit:stop_loss (-5.03%)         |
| 2024-03-26 20:15:00+00:00 | SELL | 0.025 |     69753.3 | [BTC/USDT:USDT] enter                           |
| 2024-04-02 02:30:00+00:00 | BUY  | 0.025 |       66584 | [BTC/USDT:USDT] exit:trailing_stop_loss (5.05%) |
| 2024-04-02 04:30:00+00:00 | SELL | 0.026 |     66708.1 | [BTC/USDT:USDT] enter                           |
| 2024-04-02 16:45:00+00:00 | BUY  | 0.026 |   65572.248 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.63%) |
| 2024-04-03 01:15:00+00:00 | SELL | 0.027 |     65303.5 | [BTC/USDT:USDT] enter                           |
| 2024-04-04 17:45:00+00:00 | BUY  | 0.027 |   68568.675 | [BTC/USDT:USDT] exit:stop_loss (-5.05%)         |
| 2024-04-08 03:30:00+00:00 | SELL | 0.025 |     69323.9 | [BTC/USDT:USDT] enter                           |
| 2024-04-08 12:00:00+00:00 | BUY  | 0.025 |   72790.095 | [BTC/USDT:USDT] exit:stop_loss (-5.09%)         |
| 2024-04-09 10:00:00+00:00 | SELL | 0.024 |     70442.6 | [BTC/USDT:USDT] enter                           |
| 2024-04-09 20:15:00+00:00 | BUY  | 0.024 |    69239.24 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.63%) |
| 2024-04-10 03:30:00+00:00 | SELL | 0.025 |     68935.2 | [BTC/USDT:USDT] enter                           |
| 2024-04-12 18:30:00+00:00 | BUY  | 0.025 |    66078.53 | [BTC/USDT:USDT] exit:trailing_stop_loss (4.18%) |
| 2024-04-12 20:00:00+00:00 | SELL | 0.026 |     66867.6 | [BTC/USDT:USDT] enter                           |
| 2024-04-13 19:45:00+00:00 | BUY  | 0.026 |    64482.95 | [BTC/USDT:USDT] exit:trailing_stop_loss (3.50%) |
| 2024-04-14 00:00:00+00:00 | SELL | 0.028 |     63939.7 | [BTC/USDT:USDT] enter                           |
| 2024-04-16 05:00:00+00:00 | BUY  | 0.028 |   62576.577 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.09%) |
| 2024-04-16 05:15:00+00:00 | SELL | 0.028 |     62510.5 | [BTC/USDT:USDT] enter                           |
| 2024-04-17 15:45:00+00:00 | BUY  | 0.028 |   60608.898 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.97%) |
| 2024-04-17 17:00:00+00:00 | SELL |  0.03 |       60166 | [BTC/USDT:USDT] enter                           |
| 2024-04-18 14:00:00+00:00 | BUY  |  0.03 |     63174.3 | [BTC/USDT:USDT] exit:stop_loss (-5.09%)         |
| 2024-04-20 10:00:00+00:00 | SELL | 0.028 |     63583.4 | [BTC/USDT:USDT] enter                           |
| 2024-04-22 17:15:00+00:00 | BUY  | 0.028 |    66762.57 | [BTC/USDT:USDT] exit:stop_loss (-5.08%)         |
| 2024-04-23 23:30:00+00:00 | SELL | 0.026 |     66316.3 | [BTC/USDT:USDT] enter                           |
| 2024-04-25 00:30:00+00:00 | BUY  | 0.026 |   64528.625 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.62%) |
| 2024-04-25 04:00:00+00:00 | SELL | 0.027 |     64259.9 | [BTC/USDT:USDT] enter                           |
| 2024-04-29 14:15:00+00:00 | BUY  | 0.027 |   62652.093 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.45%) |
| 2024-04-30 10:30:00+00:00 | SELL | 0.029 |       61726 | [BTC/USDT:USDT] enter                           |
| 2024-04-30 19:45:00+00:00 | BUY  | 0.029 |    60037.25 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.65%) |
| 2024-04-30 20:15:00+00:00 | SELL |  0.03 |     59837.9 | [BTC/USDT:USDT] enter                           |
| 2024-05-01 07:00:00+00:00 | BUY  |  0.03 |       58464 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.21%) |
| 2024-05-01 09:00:00+00:00 | SELL | 0.031 |       57153 | [BTC/USDT:USDT] enter                           |
| 2024-05-03 12:30:00+00:00 | BUY  | 0.031 |    60010.65 | [BTC/USDT:USDT] exit:stop_loss (-5.09%)         |
| 2024-05-06 16:45:00+00:00 | SELL | 0.028 |     63336.6 | [BTC/USDT:USDT] enter                           |
| 2024-05-09 03:00:00+00:00 | BUY  | 0.028 |   61756.254 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.44%) |
| 2024-05-09 09:00:00+00:00 | SELL | 0.029 |     61293.7 | [BTC/USDT:USDT] enter                           |
| 2024-05-15 13:30:00+00:00 | BUY  | 0.029 |   64358.385 | [BTC/USDT:USDT] exit:stop_loss (-4.99%)         |
| 2024-05-16 18:15:00+00:00 | SELL | 0.027 |     64992.4 | [BTC/USDT:USDT] enter                           |
| 2024-05-20 16:30:00+00:00 | BUY  | 0.027 |    68242.02 | [BTC/USDT:USDT] exit:stop_loss (-5.07%)         |
| 2024-05-22 05:15:00+00:00 | SELL | 0.025 |     69759.5 | [BTC/USDT:USDT] enter                           |
| 2024-05-23 20:00:00+00:00 | BUY  | 0.025 |   67148.949 | [BTC/USDT:USDT] exit:trailing_stop_loss (3.70%) |
| 2024-05-23 21:30:00+00:00 | SELL | 0.026 |     67470.1 | [BTC/USDT:USDT] enter                           |
| 2024-06-04 16:15:00+00:00 | BUY  | 0.026 |   70843.605 | [BTC/USDT:USDT] exit:stop_loss (-4.72%)         |
| 2024-06-06 06:45:00+00:00 | SELL | 0.024 |     70900.2 | [BTC/USDT:USDT] enter                           |
| 2024-06-07 18:00:00+00:00 | BUY  | 0.024 |   69431.075 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.03%) |
| 2024-06-07 20:15:00+00:00 | SELL | 0.025 |     69136.9 | [BTC/USDT:USDT] enter                           |
| 2024-06-11 18:15:00+00:00 | BUY  | 0.025 |       66990 | [BTC/USDT:USDT] exit:trailing_stop_loss (3.13%) |
| 2024-06-13 10:30:00+00:00 | SELL | 0.026 |     67387.9 | [BTC/USDT:USDT] enter                           |
| 2024-06-14 21:15:00+00:00 | BUY  | 0.026 |   66028.186 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.96%) |
| 2024-06-15 09:45:00+00:00 | SELL | 0.026 |     66157.1 | [BTC/USDT:USDT] enter                           |
| 2024-06-18 20:45:00+00:00 | BUY  | 0.026 |   64969.947 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.79%) |
| 2024-06-19 23:30:00+00:00 | SELL | 0.027 |     64888.9 | [BTC/USDT:USDT] enter                           |
| 2024-06-24 09:30:00+00:00 | BUY  | 0.027 |     61407.5 | [BTC/USDT:USDT] exit:trailing_stop_loss (5.37%) |
| 2024-06-24 11:45:00+00:00 | SELL | 0.029 |       61140 | [BTC/USDT:USDT] enter                           |
| 2024-06-24 20:30:00+00:00 | BUY  | 0.029 |    59091.27 | [BTC/USDT:USDT] exit:trailing_stop_loss (3.26%) |
| 2024-06-26 18:15:00+00:00 | SELL |  0.03 |     61032.9 | [BTC/USDT:USDT] enter                           |
| 2024-07-04 01:30:00+00:00 | BUY  |  0.03 |    59996.65 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.82%) |
| 2024-07-04 03:15:00+00:00 | SELL | 0.031 |     58923.6 | [BTC/USDT:USDT] enter                           |
| 2024-07-04 08:30:00+00:00 | BUY  | 0.031 |       57855 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.73%) |
| 2024-07-04 10:15:00+00:00 | SELL | 0.032 |     57560.2 | [BTC/USDT:USDT] enter                           |
| 2024-07-05 02:45:00+00:00 | BUY  | 0.032 |   56181.265 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.32%) |
| 2024-07-05 05:15:00+00:00 | SELL | 0.034 |     54434.5 | [BTC/USDT:USDT] enter                           |
| 2024-07-06 13:45:00+00:00 | BUY  | 0.034 |   57156.225 | [BTC/USDT:USDT] exit:stop_loss (-5.08%)         |
| 2024-07-07 14:45:00+00:00 | SELL | 0.032 |     56765.6 | [BTC/USDT:USDT] enter                           |
| 2024-07-08 01:00:00+00:00 | BUY  | 0.032 |  55077.4525 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.89%) |
| 2024-07-08 02:00:00+00:00 | SELL | 0.033 |       54930 | [BTC/USDT:USDT] enter                           |
| 2024-07-08 08:45:00+00:00 | BUY  | 0.033 |     57676.5 | [BTC/USDT:USDT] exit:stop_loss (-5.10%)         |
| 2024-07-10 19:45:00+00:00 | SELL | 0.031 |     57461.5 | [BTC/USDT:USDT] enter                           |
| 2024-07-14 08:15:00+00:00 | BUY  | 0.031 |   60334.575 | [BTC/USDT:USDT] exit:stop_loss (-5.02%)         |
| 2024-07-17 17:30:00+00:00 | SELL | 0.028 |     64210.2 | [BTC/USDT:USDT] enter                           |
| 2024-07-20 17:15:00+00:00 | BUY  | 0.028 |    67420.71 | [BTC/USDT:USDT] exit:stop_loss (-5.09%)         |
| 2024-07-21 18:45:00+00:00 | SELL | 0.026 |       66900 | [BTC/USDT:USDT] enter                           |
| 2024-07-25 01:00:00+00:00 | BUY  | 0.026 |   65196.698 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.52%) |
| 2024-07-25 03:00:00+00:00 | SELL | 0.027 |       64188 | [BTC/USDT:USDT] enter                           |
| 2024-07-26 03:00:00+00:00 | BUY  | 0.027 |     67397.4 | [BTC/USDT:USDT] exit:stop_loss (-5.07%)         |
| 2024-07-28 03:45:00+00:00 | SELL | 0.025 |     67987.8 | [BTC/USDT:USDT] enter                           |
| 2024-07-30 01:15:00+00:00 | BUY  | 0.025 |     66807.3 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.68%) |
| 2024-07-30 02:15:00+00:00 | SELL | 0.026 |     66387.7 | [BTC/USDT:USDT] enter                           |
| 2024-08-01 08:30:00+00:00 | BUY  | 0.026 |  64512.8925 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.77%) |
| 2024-08-01 17:00:00+00:00 | SELL | 0.028 |       62890 | [BTC/USDT:USDT] enter                           |
| 2024-08-03 02:00:00+00:00 | BUY  | 0.028 |  61380.3995 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.34%) |
| 2024-08-03 17:00:00+00:00 | SELL | 0.029 |     60892.6 | [BTC/USDT:USDT] enter                           |
| 2024-08-04 17:30:00+00:00 | BUY  | 0.029 |     57895.6 | [BTC/USDT:USDT] exit:trailing_stop_loss (4.85%) |
| 2024-08-04 18:15:00+00:00 | SELL | 0.031 |     58188.2 | [BTC/USDT:USDT] enter                           |
| 2024-08-05 00:45:00+00:00 | BUY  | 0.031 |    56484.75 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.84%) |
| 2024-08-05 02:30:00+00:00 | SELL | 0.034 |     54099.3 | [BTC/USDT:USDT] enter                           |
| 2024-08-05 05:00:00+00:00 | BUY  | 0.034 |    53005.33 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.92%) |
| 2024-08-05 05:30:00+00:00 | SELL | 0.034 |       53412 | [BTC/USDT:USDT] enter                           |
| 2024-08-05 06:00:00+00:00 | BUY  | 0.034 |    52138.52 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.29%) |
| 2024-08-05 07:00:00+00:00 | SELL | 0.036 |       51562 | [BTC/USDT:USDT] enter                           |
| 2024-08-05 12:30:00+00:00 | BUY  | 0.036 |    50484.07 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.00%) |
| 2024-08-07 17:15:00+00:00 | SELL | 0.033 |     55919.2 | [BTC/USDT:USDT] enter                           |
| 2024-08-08 14:45:00+00:00 | BUY  | 0.033 |    58715.16 | [BTC/USDT:USDT] exit:stop_loss (-5.10%)         |
| 2024-08-10 02:15:00+00:00 | SELL |  0.03 |       60522 | [BTC/USDT:USDT] enter                           |
| 2024-08-11 22:00:00+00:00 | BUY  |  0.03 |   59129.231 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.20%) |
| 2024-08-11 22:15:00+00:00 | SELL | 0.031 |     58587.9 | [BTC/USDT:USDT] enter                           |
| 2024-08-13 17:30:00+00:00 | BUY  | 0.031 |   61517.295 | [BTC/USDT:USDT] exit:stop_loss (-5.09%)         |
| 2024-08-14 17:00:00+00:00 | SELL |  0.03 |     59090.5 | [BTC/USDT:USDT] enter                           |
| 2024-08-15 19:00:00+00:00 | BUY  |  0.03 |       57855 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.98%) |
| 2024-08-15 20:45:00+00:00 | SELL | 0.032 |       56814 | [BTC/USDT:USDT] enter                           |
| 2024-08-16 19:15:00+00:00 | BUY  | 0.032 |     59654.7 | [BTC/USDT:USDT] exit:stop_loss (-5.12%)         |
| 2024-08-19 01:15:00+00:00 | SELL | 0.031 |     58426.2 | [BTC/USDT:USDT] enter                           |
| 2024-08-20 05:15:00+00:00 | BUY  | 0.031 |    61347.51 | [BTC/USDT:USDT] exit:stop_loss (-5.12%)         |
| 2024-08-21 00:45:00+00:00 | SELL |  0.03 |     59078.1 | [BTC/USDT:USDT] enter                           |
| 2024-08-23 14:00:00+00:00 | BUY  |  0.03 |   62032.005 | [BTC/USDT:USDT] exit:stop_loss (-5.11%)         |
| 2024-08-25 08:15:00+00:00 | SELL | 0.027 |     63862.1 | [BTC/USDT:USDT] enter                           |
| 2024-08-27 21:45:00+00:00 | BUY  | 0.027 |  60475.4255 | [BTC/USDT:USDT] exit:trailing_stop_loss (5.23%) |
| 2024-08-28 00:15:00+00:00 | SELL |  0.03 |     59290.3 | [BTC/USDT:USDT] enter                           |
| 2024-09-01 14:00:00+00:00 | BUY  |  0.03 |   57979.845 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.13%) |
| 2024-09-01 15:30:00+00:00 | SELL | 0.031 |     57822.7 | [BTC/USDT:USDT] enter                           |
| 2024-09-04 01:00:00+00:00 | BUY  | 0.031 |   56388.325 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.40%) |
| 2024-09-04 02:15:00+00:00 | SELL | 0.031 |     56622.8 | [BTC/USDT:USDT] enter                           |
| 2024-09-06 17:15:00+00:00 | BUY  | 0.031 |     54383.7 | [BTC/USDT:USDT] exit:trailing_stop_loss (3.88%) |
| 2024-09-06 17:45:00+00:00 | SELL | 0.033 |     53918.4 | [BTC/USDT:USDT] enter                           |
| 2024-09-09 17:00:00+00:00 | BUY  | 0.033 |    56614.32 | [BTC/USDT:USDT] exit:stop_loss (-5.15%)         |
| 2024-09-11 05:00:00+00:00 | SELL | 0.031 |     56500.1 | [BTC/USDT:USDT] enter                           |
| 2024-09-13 15:30:00+00:00 | BUY  | 0.031 |   59325.105 | [BTC/USDT:USDT] exit:stop_loss (-5.12%)         |
| 2024-09-15 20:45:00+00:00 | SELL | 0.029 |     59753.1 | [BTC/USDT:USDT] enter                           |
| 2024-09-16 23:45:00+00:00 | BUY  | 0.029 |  58307.9945 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.33%) |
| 2024-09-17 01:45:00+00:00 | SELL |  0.03 |     57907.6 | [BTC/USDT:USDT] enter                           |
| 2024-09-17 15:00:00+00:00 | BUY  |  0.03 |    60802.98 | [BTC/USDT:USDT] exit:stop_loss (-5.10%)         |
| 2024-09-18 16:15:00+00:00 | SELL | 0.029 |     59465.3 | [BTC/USDT:USDT] enter                           |
| 2024-09-19 00:45:00+00:00 | BUY  | 0.029 |   62438.565 | [BTC/USDT:USDT] exit:stop_loss (-5.10%)         |
| 2024-09-20 15:15:00+00:00 | SELL | 0.027 |     62903.2 | [BTC/USDT:USDT] enter                           |
| 2024-09-27 14:00:00+00:00 | BUY  | 0.027 |    66048.36 | [BTC/USDT:USDT] exit:stop_loss (-5.00%)         |
| 2024-09-28 09:45:00+00:00 | SELL | 0.025 |     65562.1 | [BTC/USDT:USDT] enter                           |
| 2024-10-01 04:00:00+00:00 | BUY  | 0.025 |   63767.375 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.68%) |
| 2024-10-01 16:30:00+00:00 | SELL | 0.027 |       62309 | [BTC/USDT:USDT] enter                           |
| 2024-10-01 21:45:00+00:00 | BUY  | 0.027 |   61030.123 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.95%) |
| 2024-10-01 22:30:00+00:00 | SELL | 0.028 |       60806 | [BTC/USDT:USDT] enter                           |
| 2024-10-07 01:00:00+00:00 | BUY  | 0.028 |     63846.3 | [BTC/USDT:USDT] exit:stop_loss (-5.05%)         |
| 2024-10-08 00:30:00+00:00 | SELL | 0.027 |       62360 | [BTC/USDT:USDT] enter                           |
| 2024-10-10 10:30:00+00:00 | BUY  | 0.027 |  61155.6785 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.87%) |
| 2024-10-10 15:15:00+00:00 | SELL | 0.028 |     60732.4 | [BTC/USDT:USDT] enter                           |
| 2024-10-14 03:30:00+00:00 | BUY  | 0.028 |    63769.02 | [BTC/USDT:USDT] exit:stop_loss (-5.07%)         |
| 2024-10-17 11:15:00+00:00 | SELL | 0.025 |     67065.8 | [BTC/USDT:USDT] enter                           |
| 2024-10-29 02:00:00+00:00 | BUY  | 0.025 |    70419.09 | [BTC/USDT:USDT] exit:stop_loss (-4.76%)         |
| 2024-10-30 17:15:00+00:00 | SELL | 0.022 |     71873.1 | [BTC/USDT:USDT] enter                           |
| 2024-11-01 10:15:00+00:00 | BUY  | 0.022 |   69903.456 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.69%) |
| 2024-11-01 21:00:00+00:00 | SELL | 0.024 |     69258.9 | [BTC/USDT:USDT] enter                           |
| 2024-11-04 22:15:00+00:00 | BUY  | 0.024 |    67812.15 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.08%) |
| 2024-11-13 05:45:00+00:00 | SELL | 0.019 |     86980.3 | [BTC/USDT:USDT] enter                           |
| 2024-11-13 14:45:00+00:00 | BUY  | 0.019 |   91329.315 | [BTC/USDT:USDT] exit:stop_loss (-5.09%)         |
| 2024-11-14 16:30:00+00:00 | SELL | 0.018 |     88269.1 | [BTC/USDT:USDT] enter                           |
| 2024-11-18 15:45:00+00:00 | BUY  | 0.018 |   92682.555 | [BTC/USDT:USDT] exit:stop_loss (-4.95%)         |
| 2024-11-23 04:15:00+00:00 | SELL | 0.016 |     98612.6 | [BTC/USDT:USDT] enter                           |
| 2024-11-25 15:15:00+00:00 | BUY  | 0.016 |   96085.381 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.56%) |
| 2024-11-25 16:45:00+00:00 | SELL | 0.017 |     95927.4 | [BTC/USDT:USDT] enter                           |
| 2024-11-25 22:45:00+00:00 | BUY  | 0.017 |    94055.99 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.85%) |
| 2024-11-25 23:30:00+00:00 | SELL | 0.017 |     93740.1 | [BTC/USDT:USDT] enter                           |
| 2024-11-26 22:00:00+00:00 | BUY  | 0.017 |   92229.396 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.58%) |
| 2024-11-26 23:00:00+00:00 | SELL | 0.017 |       91888 | [BTC/USDT:USDT] enter                           |
| 2024-11-27 18:00:00+00:00 | BUY  | 0.017 |     96482.4 | [BTC/USDT:USDT] exit:stop_loss (-5.05%)         |
| 2024-11-28 18:00:00+00:00 | SELL | 0.017 |     94927.3 | [BTC/USDT:USDT] enter                           |
| 2024-12-05 02:30:00+00:00 | BUY  | 0.017 |   99673.665 | [BTC/USDT:USDT] exit:stop_loss (-4.74%)         |
| 2024-12-05 23:45:00+00:00 | SELL | 0.016 |     96444.1 | [BTC/USDT:USDT] enter                           |
| 2024-12-06 17:45:00+00:00 | BUY  | 0.016 |  101266.305 | [BTC/USDT:USDT] exit:stop_loss (-5.07%)         |
| 2024-12-08 09:30:00+00:00 | SELL | 0.015 |     99347.6 | [BTC/USDT:USDT] enter                           |
| 2024-12-09 21:00:00+00:00 | BUY  | 0.015 |  95450.2955 | [BTC/USDT:USDT] exit:trailing_stop_loss (3.91%) |
| 2024-12-09 21:15:00+00:00 | SELL | 0.016 |       96592 | [BTC/USDT:USDT] enter                           |
| 2024-12-11 20:15:00+00:00 | BUY  | 0.016 |    101421.6 | [BTC/USDT:USDT] exit:stop_loss (-5.04%)         |
| 2024-12-12 21:45:00+00:00 | SELL | 0.015 |     99792.4 | [BTC/USDT:USDT] enter                           |
| 2024-12-15 23:15:00+00:00 | BUY  | 0.015 |   104782.02 | [BTC/USDT:USDT] exit:stop_loss (-5.02%)         |
| 2024-12-17 23:00:00+00:00 | SELL | 0.014 |    105907.5 | [BTC/USDT:USDT] enter                           |
| 2024-12-18 20:00:00+00:00 | BUY  | 0.014 |  102191.215 | [BTC/USDT:USDT] exit:trailing_stop_loss (3.44%) |
| 2024-12-18 21:30:00+00:00 | SELL | 0.015 |    101222.6 | [BTC/USDT:USDT] enter                           |
| 2024-12-19 17:45:00+00:00 | BUY  | 0.015 |  98848.5155 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.28%) |
| 2024-12-19 19:30:00+00:00 | SELL | 0.016 |     98112.8 | [BTC/USDT:USDT] enter                           |
| 2024-12-20 12:15:00+00:00 | BUY  | 0.016 |    93716.98 | [BTC/USDT:USDT] exit:trailing_stop_loss (4.40%) |
| 2024-12-21 17:00:00+00:00 | SELL | 0.016 |     97259.2 | [BTC/USDT:USDT] enter                           |
| 2024-12-22 23:00:00+00:00 | BUY  | 0.016 |       95613 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.62%) |
| 2024-12-22 23:45:00+00:00 | SELL | 0.016 |     95094.3 | [BTC/USDT:USDT] enter                           |
| 2024-12-26 00:00:00+00:00 | BUY  | 0.016 |   99849.015 | [BTC/USDT:USDT] exit:stop_loss (-5.00%)         |
| 2024-12-26 10:30:00+00:00 | SELL | 0.016 |     95472.6 | [BTC/USDT:USDT] enter                           |
| 2024-12-30 17:30:00+00:00 | BUY  | 0.016 |    92882.65 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.72%) |
| 2024-12-31 01:00:00+00:00 | SELL | 0.017 |     92435.9 | [BTC/USDT:USDT] enter                           |
| 2025-01-02 14:30:00+00:00 | BUY  | 0.017 |   97057.695 | [BTC/USDT:USDT] exit:stop_loss (-5.03%)         |
| 2025-01-03 10:45:00+00:00 | SELL | 0.016 |     96441.5 | [BTC/USDT:USDT] enter                           |
| 2025-01-06 15:15:00+00:00 | BUY  | 0.016 |  101263.575 | [BTC/USDT:USDT] exit:stop_loss (-5.03%)         |
| 2025-01-07 17:00:00+00:00 | SELL | 0.015 |     97706.4 | [BTC/USDT:USDT] enter                           |
| 2025-01-08 15:00:00+00:00 | BUY  | 0.015 |  95897.9105 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.77%) |
| 2025-01-08 15:15:00+00:00 | SELL | 0.016 |     95128.7 | [BTC/USDT:USDT] enter                           |
| 2025-01-09 15:15:00+00:00 | BUY  | 0.016 |   93123.205 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.04%) |
| 2025-01-09 18:45:00+00:00 | SELL | 0.016 |     92982.7 | [BTC/USDT:USDT] enter                           |
| 2025-01-13 14:30:00+00:00 | BUY  | 0.016 |   90242.635 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.90%) |
| 2025-01-16 15:30:00+00:00 | SELL | 0.016 |     98369.2 | [BTC/USDT:USDT] enter                           |
| 2025-01-17 14:45:00+00:00 | BUY  | 0.016 |   103287.66 | [BTC/USDT:USDT] exit:stop_loss (-5.09%)         |
| 2025-01-20 00:15:00+00:00 | SELL | 0.015 |    101373.9 | [BTC/USDT:USDT] enter                           |
| 2025-01-20 06:45:00+00:00 | BUY  | 0.015 |  106442.595 | [BTC/USDT:USDT] exit:stop_loss (-5.11%)         |
| 2025-01-20 21:30:00+00:00 | SELL | 0.014 |      103693 | [BTC/USDT:USDT] enter                           |
| 2025-01-21 01:15:00+00:00 | BUY  | 0.014 | 101734.1605 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.80%) |
| 2025-01-21 06:15:00+00:00 | SELL | 0.015 |    101780.1 | [BTC/USDT:USDT] enter                           |
| 2025-01-21 18:30:00+00:00 | BUY  | 0.015 |  106869.105 | [BTC/USDT:USDT] exit:stop_loss (-5.08%)         |
| 2025-01-22 14:30:00+00:00 | SELL | 0.014 |    104614.4 | [BTC/USDT:USDT] enter                           |
| 2025-01-23 14:30:00+00:00 | BUY  | 0.014 |  102729.165 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.73%) |
| 2025-01-25 06:15:00+00:00 | SELL | 0.014 |    104384.3 | [BTC/USDT:USDT] enter                           |
| 2025-01-27 07:30:00+00:00 | BUY  | 0.014 |     99145.2 | [BTC/USDT:USDT] exit:trailing_stop_loss (4.98%) |
| 2025-01-27 07:45:00+00:00 | SELL | 0.015 |     99114.9 | [BTC/USDT:USDT] enter                           |
| 2025-01-29 20:15:00+00:00 | BUY  | 0.015 |  104070.645 | [BTC/USDT:USDT] exit:stop_loss (-5.05%)         |
| 2025-01-31 04:45:00+00:00 | SELL | 0.014 |      104200 | [BTC/USDT:USDT] enter                           |
| 2025-02-02 19:30:00+00:00 | BUY  | 0.014 |  98201.3515 | [BTC/USDT:USDT] exit:trailing_stop_loss (5.71%) |
| 2025-02-02 20:45:00+00:00 | SELL | 0.015 |     97912.7 | [BTC/USDT:USDT] enter                           |
| 2025-02-03 01:30:00+00:00 | BUY  | 0.015 |    95156.25 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.73%) |
| 2025-02-03 02:45:00+00:00 | SELL | 0.016 |     93847.5 | [BTC/USDT:USDT] enter                           |
| 2025-02-03 15:30:00+00:00 | BUY  | 0.016 |   98539.875 | [BTC/USDT:USDT] exit:stop_loss (-5.09%)         |
| 2025-02-04 22:30:00+00:00 | SELL | 0.015 |     96901.3 | [BTC/USDT:USDT] enter                           |
| 2025-02-18 21:00:00+00:00 | BUY  | 0.015 |   94721.424 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.33%) |
| 2025-02-21 20:45:00+00:00 | SELL | 0.016 |     95332.1 | [BTC/USDT:USDT] enter                           |
| 2025-02-25 01:30:00+00:00 | BUY  | 0.016 |    92212.75 | [BTC/USDT:USDT] exit:trailing_stop_loss (3.22%) |
| 2025-02-25 02:15:00+00:00 | SELL | 0.016 |     91771.2 | [BTC/USDT:USDT] enter                           |
| 2025-02-25 07:15:00+00:00 | BUY  | 0.016 |     90192.9 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.62%) |
| 2025-02-25 08:15:00+00:00 | SELL | 0.017 |       89799 | [BTC/USDT:USDT] enter                           |
| 2025-02-25 10:30:00+00:00 | BUY  | 0.017 |       88102 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.79%) |
| 2025-02-25 11:00:00+00:00 | SELL | 0.017 |     88164.5 | [BTC/USDT:USDT] enter                           |
| 2025-02-26 14:30:00+00:00 | BUY  | 0.017 |   86657.858 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.62%) |
| 2025-02-26 16:45:00+00:00 | SELL | 0.018 |     87187.8 | [BTC/USDT:USDT] enter                           |
| 2025-02-26 18:30:00+00:00 | BUY  | 0.018 |  84514.4825 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.97%) |
| 2025-02-26 20:30:00+00:00 | SELL | 0.019 |     83489.7 | [BTC/USDT:USDT] enter                           |
| 2025-02-28 02:30:00+00:00 | BUY  | 0.019 |     80692.5 | [BTC/USDT:USDT] exit:trailing_stop_loss (3.28%) |
| 2025-02-28 03:30:00+00:00 | SELL | 0.019 |     80892.4 | [BTC/USDT:USDT] enter                           |
| 2025-02-28 09:00:00+00:00 | BUY  | 0.019 |   79373.203 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.79%) |
| 2025-03-03 18:00:00+00:00 | SELL | 0.017 |       90258 | [BTC/USDT:USDT] enter                           |
| 2025-03-03 18:15:00+00:00 | BUY  | 0.017 |    88668.37 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.66%) |
| 2025-03-03 21:00:00+00:00 | SELL | 0.018 |       86032 | [BTC/USDT:USDT] enter                           |
| 2025-03-04 02:00:00+00:00 | BUY  | 0.018 |     83656.3 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.66%) |
| 2025-03-04 04:30:00+00:00 | SELL | 0.019 |     83747.4 | [BTC/USDT:USDT] enter                           |
| 2025-03-04 19:00:00+00:00 | BUY  | 0.019 |    87934.77 | [BTC/USDT:USDT] exit:stop_loss (-5.10%)         |
| 2025-03-06 18:15:00+00:00 | SELL | 0.018 |     88611.9 | [BTC/USDT:USDT] enter                           |
| 2025-03-07 00:30:00+00:00 | BUY  | 0.018 |  86824.6225 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.92%) |
| 2025-03-07 01:30:00+00:00 | SELL | 0.018 |     87064.3 | [BTC/USDT:USDT] enter                           |
| 2025-03-09 20:30:00+00:00 | BUY  | 0.018 |  83409.5535 | [BTC/USDT:USDT] exit:trailing_stop_loss (4.12%) |
| 2025-03-09 23:45:00+00:00 | SELL |  0.02 |       80600 | [BTC/USDT:USDT] enter                           |
| 2025-03-10 19:15:00+00:00 | BUY  |  0.02 |  78571.2515 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.43%) |
| 2025-03-13 14:45:00+00:00 | SELL |  0.02 |     81991.7 | [BTC/USDT:USDT] enter                           |
| 2025-03-19 22:30:00+00:00 | BUY  |  0.02 |   86091.285 | [BTC/USDT:USDT] exit:stop_loss (-5.07%)         |
| 2025-03-20 17:15:00+00:00 | SELL | 0.019 |     84123.5 | [BTC/USDT:USDT] enter                           |
| 2025-03-24 14:00:00+00:00 | BUY  | 0.019 |   88329.675 | [BTC/USDT:USDT] exit:stop_loss (-5.08%)         |
| 2025-03-25 04:45:00+00:00 | SELL | 0.018 |     86454.3 | [BTC/USDT:USDT] enter                           |
| 2025-03-30 00:45:00+00:00 | BUY  | 0.018 |   82825.015 | [BTC/USDT:USDT] exit:trailing_stop_loss (4.12%) |
| 2025-03-30 20:45:00+00:00 | SELL | 0.019 |     82552.6 | [BTC/USDT:USDT] enter                           |
| 2025-04-02 15:30:00+00:00 | BUY  | 0.019 |    86680.23 | [BTC/USDT:USDT] exit:stop_loss (-5.08%)         |
| 2025-04-03 00:00:00+00:00 | SELL | 0.019 |     82485.1 | [BTC/USDT:USDT] enter                           |
| 2025-04-06 20:00:00+00:00 | BUY  | 0.019 |   79814.525 | [BTC/USDT:USDT] exit:trailing_stop_loss (3.20%) |
| 2025-04-06 20:30:00+00:00 | SELL |  0.02 |     79327.8 | [BTC/USDT:USDT] enter                           |
| 2025-04-07 06:15:00+00:00 | BUY  |  0.02 |   76810.125 | [BTC/USDT:USDT] exit:trailing_stop_loss (3.08%) |
| 2025-04-07 07:45:00+00:00 | SELL | 0.021 |     75194.9 | [BTC/USDT:USDT] enter                           |
| 2025-04-07 14:00:00+00:00 | BUY  | 0.021 |   78954.645 | [BTC/USDT:USDT] exit:stop_loss (-5.10%)         |
| 2025-04-08 16:30:00+00:00 | SELL |  0.02 |     78087.5 | [BTC/USDT:USDT] enter                           |
| 2025-04-09 01:00:00+00:00 | BUY  |  0.02 |   76364.743 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.12%) |
| 2025-04-09 02:45:00+00:00 | SELL | 0.021 |     75554.1 | [BTC/USDT:USDT] enter                           |
| 2025-04-09 17:15:00+00:00 | BUY  | 0.021 |   79331.805 | [BTC/USDT:USDT] exit:stop_loss (-5.10%)         |
| 2025-04-10 19:30:00+00:00 | SELL |  0.02 |     79323.3 | [BTC/USDT:USDT] enter                           |
| 2025-04-11 13:30:00+00:00 | BUY  |  0.02 |   83289.465 | [BTC/USDT:USDT] exit:stop_loss (-5.11%)         |
| 2025-04-13 15:15:00+00:00 | SELL | 0.018 |     83776.1 | [BTC/USDT:USDT] enter                           |
| 2025-04-21 14:15:00+00:00 | BUY  | 0.018 |   87964.905 | [BTC/USDT:USDT] exit:stop_loss (-5.02%)         |
| 2025-04-24 05:00:00+00:00 | SELL | 0.016 |     92706.1 | [BTC/USDT:USDT] enter                           |
| 2025-05-01 15:00:00+00:00 | BUY  | 0.016 |   97341.405 | [BTC/USDT:USDT] exit:stop_loss (-5.12%)         |
| 2025-05-03 02:45:00+00:00 | SELL | 0.015 |     96515.7 | [BTC/USDT:USDT] enter                           |
| 2025-05-05 18:30:00+00:00 | BUY  | 0.015 |  94846.7765 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.64%) |
| 2025-05-06 10:15:00+00:00 | SELL | 0.016 |     94120.1 | [BTC/USDT:USDT] enter                           |
| 2025-05-08 03:00:00+00:00 | BUY  | 0.016 |   98826.105 | [BTC/USDT:USDT] exit:stop_loss (-5.10%)         |
| 2025-05-10 21:00:00+00:00 | SELL | 0.014 |    103144.9 | [BTC/USDT:USDT] enter                           |
| 2025-05-21 14:45:00+00:00 | BUY  | 0.014 |  108302.145 | [BTC/USDT:USDT] exit:stop_loss (-4.91%)         |
| 2025-05-23 06:45:00+00:00 | SELL | 0.013 |    110611.2 | [BTC/USDT:USDT] enter                           |
| 2025-05-24 03:30:00+00:00 | BUY  | 0.013 | 108322.7285 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.99%) |
| 2025-05-25 02:15:00+00:00 | SELL | 0.013 |    107523.1 | [BTC/USDT:USDT] enter                           |
| 2025-05-31 15:00:00+00:00 | BUY  | 0.013 | 104577.5815 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.75%) |
| 2025-06-02 12:30:00+00:00 | SELL | 0.014 |    104004.7 | [BTC/USDT:USDT] enter                           |
| 2025-06-06 00:45:00+00:00 | BUY  | 0.014 | 101809.6765 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.04%) |
| 2025-06-09 06:15:00+00:00 | SELL | 0.014 |    105346.4 | [BTC/USDT:USDT] enter                           |
| 2025-06-09 21:30:00+00:00 | BUY  | 0.014 |   110613.72 | [BTC/USDT:USDT] exit:stop_loss (-5.10%)         |
| 2025-06-11 11:30:00+00:00 | SELL | 0.013 |      109220 | [BTC/USDT:USDT] enter                           |
| 2025-06-13 00:00:00+00:00 | BUY  | 0.013 | 105497.7805 | [BTC/USDT:USDT] exit:trailing_stop_loss (3.32%) |
| 2025-06-13 01:45:00+00:00 | SELL | 0.014 |    103479.9 | [BTC/USDT:USDT] enter                           |
| 2025-06-16 19:00:00+00:00 | BUY  | 0.014 |  108653.895 | [BTC/USDT:USDT] exit:stop_loss (-5.08%)         |
| 2025-06-17 09:00:00+00:00 | SELL | 0.013 |    106518.8 | [BTC/USDT:USDT] enter                           |
| 2025-06-20 20:15:00+00:00 | BUY  | 0.013 | 103789.1295 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.49%) |
| 2025-06-21 00:15:00+00:00 | SELL | 0.014 |    103097.7 | [BTC/USDT:USDT] enter                           |
| 2025-06-22 17:00:00+00:00 | BUY  | 0.014 | 100088.0335 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.85%) |
| 2025-06-22 18:15:00+00:00 | SELL | 0.015 |       99367 | [BTC/USDT:USDT] enter                           |
| 2025-06-23 22:00:00+00:00 | BUY  | 0.015 |   104335.35 | [BTC/USDT:USDT] exit:stop_loss (-5.10%)         |
| 2025-06-26 14:15:00+00:00 | SELL | 0.013 |    106992.1 | [BTC/USDT:USDT] enter                           |
| 2025-07-10 16:15:00+00:00 | BUY  | 0.013 |  112341.705 | [BTC/USDT:USDT] exit:stop_loss (-4.96%)         |
| 2025-07-12 16:15:00+00:00 | SELL | 0.012 |    117240.4 | [BTC/USDT:USDT] enter                           |
| 2025-07-14 07:30:00+00:00 | BUY  | 0.012 |   123102.42 | [BTC/USDT:USDT] exit:stop_loss (-5.07%)         |
| 2025-07-15 04:30:00+00:00 | SELL | 0.012 |    117301.8 | [BTC/USDT:USDT] enter                           |
| 2025-08-01 02:30:00+00:00 | BUY  | 0.012 |  115952.585 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.55%) |
| 2025-08-01 08:45:00+00:00 | SELL | 0.012 |    114541.3 | [BTC/USDT:USDT] enter                           |
| 2025-08-11 02:00:00+00:00 | BUY  | 0.012 |  120268.365 | [BTC/USDT:USDT] exit:stop_loss (-4.92%)         |
| 2025-08-11 23:30:00+00:00 | SELL | 0.011 |    118638.2 | [BTC/USDT:USDT] enter                           |
| 2025-08-18 17:15:00+00:00 | BUY  | 0.011 |  116324.075 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.00%) |
| 2025-08-19 05:45:00+00:00 | SELL | 0.012 |      115055 | [BTC/USDT:USDT] enter                           |
| 2025-08-24 19:30:00+00:00 | BUY  | 0.012 |   112141.26 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.55%) |
| 2025-08-24 20:45:00+00:00 | SELL | 0.012 |    112960.1 | [BTC/USDT:USDT] enter                           |
| 2025-08-26 04:30:00+00:00 | BUY  | 0.012 | 110188.0955 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.39%) |
| 2025-08-26 13:45:00+00:00 | SELL | 0.013 |    109851.1 | [BTC/USDT:USDT] enter                           |
| 2025-09-11 23:45:00+00:00 | BUY  | 0.013 |  115343.655 | [BTC/USDT:USDT] exit:stop_loss (-4.82%)         |
| 2025-09-14 15:00:00+00:00 | SELL | 0.012 |    115350.8 | [BTC/USDT:USDT] enter                           |
| 2025-09-22 06:00:00+00:00 | BUY  | 0.012 |  113141.238 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.92%) |
| 2025-09-22 07:30:00+00:00 | SELL | 0.012 |      112730 | [BTC/USDT:USDT] enter                           |
| 2025-09-26 18:15:00+00:00 | BUY  | 0.012 |   110194.49 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.22%) |
| 2025-10-04 17:00:00+00:00 | SELL | 0.011 |    121668.4 | [BTC/USDT:USDT] enter                           |
| 2025-10-10 20:45:00+00:00 | BUY  | 0.011 |  114478.399 | [BTC/USDT:USDT] exit:trailing_stop_loss (5.92%) |
| 2025-10-10 22:00:00+00:00 | SELL | 0.012 |    113253.6 | [BTC/USDT:USDT] enter                           |
| 2025-10-11 22:30:00+00:00 | BUY  | 0.012 |  111143.515 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.79%) |
| 2025-10-11 23:15:00+00:00 | SELL | 0.013 |    110836.9 | [BTC/USDT:USDT] enter                           |
| 2025-10-17 01:00:00+00:00 | BUY  | 0.013 |   108960.25 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.56%) |
| 2025-10-17 09:15:00+00:00 | SELL | 0.014 |      105190 | [BTC/USDT:USDT] enter                           |
| 2025-10-20 04:00:00+00:00 | BUY  | 0.014 |    110449.5 | [BTC/USDT:USDT] exit:stop_loss (-5.12%)         |
| 2025-10-21 06:15:00+00:00 | SELL | 0.013 |    107595.9 | [BTC/USDT:USDT] enter                           |
| 2025-10-21 15:15:00+00:00 | BUY  | 0.013 |  112975.695 | [BTC/USDT:USDT] exit:stop_loss (-5.10%)         |
| 2025-10-22 02:45:00+00:00 | SELL | 0.013 |    108249.3 | [BTC/USDT:USDT] enter                           |
| 2025-10-26 12:00:00+00:00 | BUY  | 0.013 |  113661.765 | [BTC/USDT:USDT] exit:stop_loss (-5.06%)         |
| 2025-10-27 23:45:00+00:00 | SELL | 0.012 |    114093.3 | [BTC/USDT:USDT] enter                           |
| 2025-10-29 18:30:00+00:00 | BUY  | 0.012 |  110661.796 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.94%) |
| 2025-10-29 19:30:00+00:00 | SELL | 0.012 |    110899.9 | [BTC/USDT:USDT] enter                           |
| 2025-10-30 21:30:00+00:00 | BUY  | 0.012 |      107793 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.71%) |
| 2025-11-02 20:00:00+00:00 | SELL | 0.013 |    110125.3 | [BTC/USDT:USDT] enter                           |
| 2025-11-03 14:00:00+00:00 | BUY  | 0.013 | 108217.9805 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.65%) |
| 2025-11-03 16:30:00+00:00 | SELL | 0.013 |      106328 | [BTC/USDT:USDT] enter                           |
| 2025-11-04 14:45:00+00:00 | BUY  | 0.013 |   104413.05 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.72%) |
| 2025-11-04 19:45:00+00:00 | SELL | 0.014 |    100781.5 | [BTC/USDT:USDT] enter                           |
| 2025-11-10 00:30:00+00:00 | BUY  | 0.014 |  105820.575 | [BTC/USDT:USDT] exit:stop_loss (-5.02%)         |
| 2025-11-11 07:45:00+00:00 | SELL | 0.013 |    104880.1 | [BTC/USDT:USDT] enter                           |
| 2025-11-13 01:00:00+00:00 | BUY  | 0.013 |  102221.665 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.45%) |
| 2025-11-13 19:45:00+00:00 | SELL | 0.014 |     98873.6 | [BTC/USDT:USDT] enter                           |
| 2025-11-14 14:30:00+00:00 | BUY  | 0.014 |     95917.5 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.91%) |
| 2025-11-14 21:15:00+00:00 | SELL | 0.015 |     94851.1 | [BTC/USDT:USDT] enter                           |
| 2025-11-18 05:15:00+00:00 | BUY  | 0.015 |    90347.18 | [BTC/USDT:USDT] exit:trailing_stop_loss (4.74%) |
| 2025-11-18 05:30:00+00:00 | SELL | 0.016 |     90155.7 | [BTC/USDT:USDT] enter                           |
| 2025-11-20 17:00:00+00:00 | BUY  | 0.016 |     88000.5 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.35%) |
| 2025-11-20 18:00:00+00:00 | SELL | 0.017 |     87186.1 | [BTC/USDT:USDT] enter                           |
| 2025-11-21 07:30:00+00:00 | BUY  | 0.017 |   82327.665 | [BTC/USDT:USDT] exit:trailing_stop_loss (5.48%) |
| 2025-11-21 09:15:00+00:00 | SELL | 0.018 |     83677.5 | [BTC/USDT:USDT] enter                           |
| 2025-11-21 12:15:00+00:00 | BUY  | 0.018 |       81809 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.14%) |
| 2025-11-24 10:45:00+00:00 | SELL | 0.017 |     85902.6 | [BTC/USDT:USDT] enter                           |
| 2025-11-26 18:15:00+00:00 | BUY  | 0.017 |    90197.73 | [BTC/USDT:USDT] exit:stop_loss (-5.10%)         |
| 2025-11-28 02:45:00+00:00 | SELL | 0.016 |     90777.5 | [BTC/USDT:USDT] enter                           |
| 2025-12-01 09:00:00+00:00 | BUY  | 0.016 |  86847.1555 | [BTC/USDT:USDT] exit:trailing_stop_loss (4.26%) |
| 2025-12-01 13:45:00+00:00 | SELL | 0.017 |     85746.2 | [BTC/USDT:USDT] enter                           |
| 2025-12-02 15:00:00+00:00 | BUY  | 0.017 |    90033.51 | [BTC/USDT:USDT] exit:stop_loss (-5.10%)         |
| 2025-12-04 14:15:00+00:00 | SELL | 0.016 |     92614.6 | [BTC/USDT:USDT] enter                           |
| 2025-12-05 17:45:00+00:00 | BUY  | 0.016 |  89295.9445 | [BTC/USDT:USDT] exit:trailing_stop_loss (3.50%) |
| 2025-12-05 18:45:00+00:00 | SELL | 0.016 |     89062.1 | [BTC/USDT:USDT] enter                           |
| 2025-12-09 16:15:00+00:00 | BUY  | 0.016 |   93515.205 | [BTC/USDT:USDT] exit:stop_loss (-5.07%)         |
| 2025-12-11 03:45:00+00:00 | SELL | 0.016 |     89779.9 | [BTC/USDT:USDT] enter                           |
| 2025-12-15 19:00:00+00:00 | BUY  | 0.016 |   86349.095 | [BTC/USDT:USDT] exit:trailing_stop_loss (3.78%) |
| 2025-12-15 20:45:00+00:00 | SELL | 0.017 |       85893 | [BTC/USDT:USDT] enter                           |
| 2025-12-17 15:00:00+00:00 | BUY  | 0.017 |    90187.65 | [BTC/USDT:USDT] exit:stop_loss (-5.08%)         |
| 2025-12-17 20:15:00+00:00 | SELL | 0.017 |     85654.9 | [BTC/USDT:USDT] enter                           |
| 2025-12-22 11:30:00+00:00 | BUY  | 0.017 |   89937.645 | [BTC/USDT:USDT] exit:stop_loss (-5.01%)         |
| 2025-12-22 22:15:00+00:00 | SELL | 0.016 |     88251.3 | [BTC/USDT:USDT] enter                           |
| 2026-01-05 01:00:00+00:00 | BUY  | 0.016 |   92663.865 | [BTC/USDT:USDT] exit:stop_loss (-4.87%)         |
| 2026-01-06 18:45:00+00:00 | SELL | 0.015 |     91904.5 | [BTC/USDT:USDT] enter                           |
| 2026-01-13 22:00:00+00:00 | BUY  | 0.015 |   96499.725 | [BTC/USDT:USDT] exit:stop_loss (-5.00%)         |
| 2026-01-15 20:15:00+00:00 | SELL | 0.014 |       95502 | [BTC/USDT:USDT] enter                           |
| 2026-01-19 00:00:00+00:00 | BUY  | 0.014 |       93177 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.38%) |
| 2026-01-19 01:45:00+00:00 | SELL | 0.015 |       92458 | [BTC/USDT:USDT] enter                           |
| 2026-01-20 22:30:00+00:00 | BUY  | 0.015 |   89104.008 | [BTC/USDT:USDT] exit:trailing_stop_loss (3.56%) |
| 2026-01-21 00:00:00+00:00 | SELL | 0.016 |     88390.7 | [BTC/USDT:USDT] enter                           |
| 2026-01-29 15:00:00+00:00 | BUY  | 0.016 |     86559.2 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.12%) |
| 2026-01-29 17:45:00+00:00 | SELL | 0.017 |     84843.8 | [BTC/USDT:USDT] enter                           |
| 2026-01-30 01:30:00+00:00 | BUY  | 0.017 |       82215 | [BTC/USDT:USDT] exit:trailing_stop_loss (3.01%) |
| 2026-01-30 03:00:00+00:00 | SELL | 0.017 |       82128 | [BTC/USDT:USDT] enter                           |
| 2026-01-31 17:00:00+00:00 | BUY  | 0.017 |  79180.2515 | [BTC/USDT:USDT] exit:trailing_stop_loss (3.51%) |
| 2026-01-31 19:15:00+00:00 | SELL | 0.018 |     78186.7 | [BTC/USDT:USDT] enter                           |
| 2026-02-01 23:00:00+00:00 | BUY  | 0.018 |    76778.66 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.70%) |
| 2026-02-01 23:30:00+00:00 | SELL | 0.019 |     76762.1 | [BTC/USDT:USDT] enter                           |
| 2026-02-03 19:00:00+00:00 | BUY  | 0.019 |     74196.5 | [BTC/USDT:USDT] exit:trailing_stop_loss (3.24%) |
| 2026-02-04 10:00:00+00:00 | SELL | 0.019 |       76082 | [BTC/USDT:USDT] enter                           |
| 2026-02-04 16:30:00+00:00 | BUY  | 0.019 |    74143.72 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.45%) |
| 2026-02-04 17:15:00+00:00 | SELL |  0.02 |       73570 | [BTC/USDT:USDT] enter                           |
| 2026-02-05 02:45:00+00:00 | BUY  |  0.02 |  72332.0465 | [BTC/USDT:USDT] exit:trailing_stop_loss (1.59%) |
| 2026-02-05 04:30:00+00:00 | SELL | 0.021 |     70997.6 | [BTC/USDT:USDT] enter                           |
| 2026-02-05 15:00:00+00:00 | BUY  | 0.021 |   68957.882 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.78%) |
| 2026-02-05 17:15:00+00:00 | SELL | 0.022 |     67229.3 | [BTC/USDT:USDT] enter                           |
| 2026-02-05 20:15:00+00:00 | BUY  | 0.022 |  64283.0965 | [BTC/USDT:USDT] exit:trailing_stop_loss (4.29%) |
| 2026-02-05 21:30:00+00:00 | SELL | 0.024 |     63954.1 | [BTC/USDT:USDT] enter                           |
| 2026-02-06 00:00:00+00:00 | BUY  | 0.024 |  60900.1015 | [BTC/USDT:USDT] exit:trailing_stop_loss (4.68%) |
| 2026-02-06 08:30:00+00:00 | SELL | 0.024 |       64775 | [BTC/USDT:USDT] enter                           |
| 2026-02-06 14:30:00+00:00 | BUY  | 0.024 |    68013.75 | [BTC/USDT:USDT] exit:stop_loss (-5.11%)         |
| 2026-02-09 11:30:00+00:00 | SELL | 0.022 |     68832.9 | [BTC/USDT:USDT] enter                           |
| 2026-02-11 12:15:00+00:00 | BUY  | 0.022 |   67337.739 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.04%) |
| 2026-02-11 16:00:00+00:00 | SELL | 0.023 |     66489.4 | [BTC/USDT:USDT] enter                           |
| 2026-02-14 08:45:00+00:00 | BUY  | 0.023 |    69813.87 | [BTC/USDT:USDT] exit:stop_loss (-5.10%)         |
| 2026-02-15 15:45:00+00:00 | SELL | 0.022 |     69047.1 | [BTC/USDT:USDT] enter                           |
| 2026-02-17 16:00:00+00:00 | BUY  | 0.022 |    67586.82 | [BTC/USDT:USDT] exit:trailing_stop_loss (2.02%) |
| 2026-02-17 17:15:00+00:00 | SELL | 0.023 |     67231.7 | [BTC/USDT:USDT] enter                           |
| 2026-02-21 03:45:00+00:00 | BUY  | 0.023 |     67589.8 | [BTC/USDT:USDT] exit:force_exit (-0.62%)        |

## Deep Diagnostics

### MAE/MFE Efficiency

| Metric                      |   Value |
|-----------------------------|--------:|
| Avg MAE %                   |  3.1082 |
| Avg MFE %                   |  3.0364 |
| Profit Giveback % (winners) | 37.4402 |

MAE Distribution:

```text
0.03%..1.09% | ################## (60)
1.09%..2.15% | ########## (35)
2.15%..3.21% | ######## (25)
3.21%..4.27% | ### (11)
4.27%..5.33% | ################# (56)
5.33%..6.39% | ########## (34)
6.39%..7.45% | # (1)
7.45%..8.51% | # (3)
```

MFE Distribution:

```text
0.00%..0.91% | ############ (35)
0.91%..1.83% | ########## (29)
1.83%..2.74% | ####### (20)
2.74%..3.65% | ################## (53)
3.65%..4.56% | ################## (54)
4.56%..5.48% | ###### (17)
5.48%..6.39% | #### (11)
6.39%..7.30% | ## (6)
```

### Rejected vs Executed

| Metric                      |   Value |
|-----------------------------|--------:|
| Rejected Total              |       0 |
| Rejected Win Rate %         |     0.0 |
| Rejected Avg Hypothetical % |     0.0 |
| Executed Win Rate %         | 60.8889 |
| Executed Avg Profit %       | -0.3113 |
| Opportunity Cost (Abs)      |     0.0 |

### Market Regime

- Status:
  `failed to read market_change.feather: Missing optional dependency 'pyarrow'.  Use pip or conda to install pyarrow.`
- Rally Win Rate %: `0.0`
- Range Win Rate %: `0.0`
- Downtrend Win Rate %: `0.0`

### Diagnostic Conclusions

- Pain Point A: Avg MAE is 3.11%, stoploss pressure is high; consider tighter entry filters or risk cap near 3.5%.
- Pain Point B: Rejected trades show better hypothetical average return than executed trades, max_open_trades may be
  locking capital in lower-quality positions.

## Strategy Code

```python
from datetime import datetime

import numpy as np
import pandas as pd
import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, DecimalParameter
from pandas import DataFrame


class AMRS3_7Strategy(IStrategy):
    """
    AMRS(ATR-Driven Mean Reversion Short 3.7

    Based on AMRS3_6Strategy with changes from AMRS3_7.md:
    - Disable exit_signal-based exits (use custom_exit only).
    - Add configurable ma25 defense with max-loss and min-age guards.
    - Add stoploss tighten-after-age cap.
    - Add breakeven / profit-protect stoploss stage.
    - Keep exit reasons explicit: atr_trailing_exit / ma25_takeprofit / ma25_defense.
    """

    INTERFACE_VERSION = 3

    minimal_roi = {
        "0": 100
    }

    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    timeframe = "15m"
    can_short = True
    process_only_new_candles = True

    use_exit_signal = False
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    startup_candle_count: int = 200

    TRENDLINE_WINDOW = 20

    consolidation_amplitude_ratio = DecimalParameter(2.0, 5.0, default=2.8, space="buy")
    consolidation_volatility_ratio = DecimalParameter(0.8, 2.0, default=0.95, space="buy")
    enable_consolidation_filter = DecimalParameter(0, 1, default=1, space="buy")

    pre_drop_multiplier = DecimalParameter(1.0, 2.0, default=1.3, space="buy")  # kept for reference
    upper_shadow_ratio = DecimalParameter(0.5, 1.2, default=0.7, space="buy")
    volume_filter_ratio = DecimalParameter(1.0, 1.5, default=1.1, space="buy")
    atr_ratio_threshold = DecimalParameter(0.4, 0.7, default=0.5, space="buy")
    min_distance_ratio = DecimalParameter(0.2, 0.5, default=0.3, space="buy")
    body_lower_ratio = DecimalParameter(0.2, 0.5, default=0.3, space="buy")
    body_upper_ratio = DecimalParameter(0.6, 1.0, default=0.8, space="buy")
    volume_burst_ratio = DecimalParameter(1.0, 1.5, default=1.0, space="buy")

    # AMRS3.5/3.6: pre-drop break level selection
    break_mode = DecimalParameter(0, 1, default=0, space="buy")  # 0=low10, 1=trendline
    break_atr_buffer = DecimalParameter(0.0, 1.5, default=0.2, space="buy")

    # Weak rebound (locked to ATR mode in 3.6)
    weak_rebound_atr = DecimalParameter(0.1, 1.5, default=0.5, space="buy")

    # Volume confirmation gate toggle
    enable_volume_confirmation = DecimalParameter(0, 1, default=1, space="buy")

    # exits
    defense_ma25_offset = DecimalParameter(1.0, 1.05, default=1.01, space="sell")
    defense_max_loss = DecimalParameter(-0.03, -0.005, default=-0.015, space="sell")
    defense_min_age_candles = DecimalParameter(1, 60, default=10, decimals=0, space="sell")

    sl_tighten_after_candles = DecimalParameter(5, 120, default=30, decimals=0, space="sell")
    sl_max_after_tighten = DecimalParameter(0.005, 0.05, default=0.02, space="sell")

    sl_breakeven_profit = DecimalParameter(0.001, 0.03, default=0.008, space="sell")
    sl_breakeven_sl = DecimalParameter(-0.005, 0.005, default=0.0, space="sell")

    ma25_offset_exit = DecimalParameter(1.0, 1.05, default=1.01, space="sell")
    atr_trailing_profit = DecimalParameter(1.0, 3.0, default=1.5, space="sell")
    atr_trailing_stop = DecimalParameter(0.5, 1.5, default=1.0, space="sell")

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._trade_sl_dict = {}

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ma7"] = ta.SMA(dataframe, timeperiod=7)
        dataframe["ma25"] = ta.SMA(dataframe, timeperiod=25)
        dataframe["ma99"] = ta.SMA(dataframe, timeperiod=99)

        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_mean"] = dataframe["atr"].rolling(window=100).mean()

        dataframe["ma7_diff"] = dataframe["ma7"].diff()
        dataframe["ma25_diff"] = dataframe["ma25"].diff()
        dataframe["ma99_diff"] = dataframe["ma99"].diff()

        dataframe["is_ma7_negative_slope"] = dataframe["ma7_diff"] < 0
        dataframe["is_ma25_negative_slope"] = dataframe["ma25_diff"] < 0
        dataframe["is_ma99_negative_slope"] = dataframe["ma99_diff"] < 0

        dataframe["high_20"] = dataframe["high"].rolling(window=20).max()
        dataframe["low_20"] = dataframe["low"].rolling(window=20).min()
        dataframe["close_std_20"] = dataframe["close"].rolling(window=20).std()

        dataframe["consolidation_amplitude"] = (dataframe["high_20"] - dataframe["low_20"]) / dataframe["atr"]
        dataframe["consolidation_volatility"] = dataframe["close_std_20"] / dataframe["atr"]

        dataframe["volume_mean"] = dataframe["volume"].rolling(window=20).mean()

        dataframe["upper_shadow"] = dataframe["high"] - np.maximum(dataframe["open"], dataframe["close"])
        dataframe["lower_shadow"] = np.minimum(dataframe["open"], dataframe["close"]) - dataframe["low"]
        dataframe["body"] = np.abs(dataframe["open"] - dataframe["close"])

        dataframe["atr_trend"] = dataframe["atr"].diff()
        dataframe["is_atr_rising"] = dataframe["atr_trend"] > 0

        dataframe["close_vs_ma7"] = np.where(dataframe["close"] < dataframe["ma7"], -1, 1)
        dataframe["close_vs_ma25"] = np.where(dataframe["close"] < dataframe["ma25"], -1, 1)
        dataframe["ma7_vs_ma25"] = np.where(dataframe["ma7"] < dataframe["ma25"], -1, 1)
        dataframe["ma25_vs_ma99"] = np.where(dataframe["ma25"] < dataframe["ma99"], -1, 1)

        dataframe["above_ma7"] = dataframe["close"] > dataframe["ma7"]
        dataframe["below_ma7"] = dataframe["close"] < dataframe["ma7"]

        dataframe["prev_close"] = dataframe["close"].shift(1)
        dataframe["prev_volume"] = dataframe["volume"].shift(1)

        dataframe["prev_high"] = dataframe["high"].shift(1)
        dataframe["prev_low"] = dataframe["low"].shift(1)
        dataframe["prev_close_above_ma7"] = dataframe["close"].shift(1) > dataframe["ma7"].shift(1)
        dataframe["prev2_close_above_ma7"] = dataframe["close"].shift(2) > dataframe["ma7"].shift(2)
        dataframe["prev3_close_above_ma7"] = dataframe["close"].shift(3) > dataframe["ma7"].shift(3)

        dataframe["high_rebound"] = dataframe["high"].rolling(window=10).max()
        dataframe["low_breakout"] = dataframe["low"].rolling(window=10).min()
        dataframe["low_10"] = dataframe["low"].rolling(window=10).min()
        dataframe["high_10"] = dataframe["high"].rolling(window=10).max()

        # Trendline of raw low using a rolling linear regression with fixed x.
        n = int(self.TRENDLINE_WINDOW)
        x = np.arange(n, dtype=float)
        x_mean = (n - 1) / 2.0
        weights = x - x_mean
        den = float(np.sum(weights ** 2)) if n > 1 else 1.0

        low_src = dataframe["low"]
        slope = low_src.rolling(window=n).apply(lambda y: float(np.dot(weights, y)) / den, raw=True)
        mean = low_src.rolling(window=n).mean()
        dataframe["trendline_slope"] = slope
        dataframe["trendline_low"] = mean + slope * ((n - 1) - x_mean)

        dataframe["atr_ratio"] = dataframe["atr"] / dataframe["atr_mean"]
        dataframe["timeout_candles"] = (10 * dataframe["atr_ratio"]).round()

        # Precompute debug + signal columns for signals export.
        # Some freqtrade versions export the dataframe after indicators (before entry/exit columns),
        # so we calculate these here to support offline gate analysis.
        amp_ratio = self.consolidation_amplitude_ratio.value
        vol_ratio = self.consolidation_volatility_ratio.value
        upper_shadow = self.upper_shadow_ratio.value
        vol_filter = self.volume_filter_ratio.value
        atr_ratio_th = self.atr_ratio_threshold.value
        min_dist = self.min_distance_ratio.value
        body_low = self.body_lower_ratio.value
        body_up = self.body_upper_ratio.value
        vol_burst = self.volume_burst_ratio.value

        cond_trend_alignment = (
                (dataframe["close"] < dataframe["ma7"]) &
                (dataframe["ma7"] < dataframe["ma25"]) &
                (dataframe["ma25"] < dataframe["ma99"]) &
                (dataframe["is_ma25_negative_slope"]) &
                (dataframe["is_ma99_negative_slope"])
        )

        cond_consolidation_raw = (
                (dataframe["consolidation_amplitude"] < amp_ratio) &
                (dataframe["consolidation_volatility"] < vol_ratio)
        )
        if self.enable_consolidation_filter.value < 0.5:
            cond_consolidation = pd.Series(True, index=dataframe.index)
        else:
            cond_consolidation = cond_consolidation_raw

        buffer_atr = self.break_atr_buffer.value
        break_level_low10 = dataframe["low_10"] - buffer_atr * dataframe["atr"]
        use_trendline = self.break_mode.value >= 0.5
        trendline_ok = (dataframe["trendline_slope"] > 0) & pd.notna(dataframe["trendline_low"])
        break_level_trend = dataframe["trendline_low"] - buffer_atr * dataframe["atr"]
        break_level = np.where(use_trendline & trendline_ok, break_level_trend, break_level_low10)
        cond_pre_drop = dataframe["close"] < break_level

        cond_env = cond_trend_alignment & cond_consolidation & cond_pre_drop

        cond_A = (
                (dataframe["high"] > np.minimum(dataframe["ma7"], dataframe["ma25"])) &
                (dataframe["upper_shadow"] > upper_shadow * dataframe["atr"]) &
                (dataframe["volume"] < dataframe["volume_mean"] * vol_filter)
        )

        diff_ma7 = (dataframe["close"] - dataframe["ma7"]).abs()
        cond_weak_rebound = diff_ma7 <= (self.weak_rebound_atr.value * dataframe["atr"])
        cond_A_relaxed = cond_A | (cond_weak_rebound & (dataframe["close"] < dataframe["ma7"]))

        cond_B = (
                (
                        (dataframe["prev_close_above_ma7"].astype(bool) & dataframe["below_ma7"].astype(bool)) |
                        ((dataframe["close"].shift(2) < dataframe["ma7"].shift(2)) & dataframe["below_ma7"].astype(
                            bool)) |
                        ((dataframe["close"].shift(3) < dataframe["ma7"].shift(3)) & dataframe["below_ma7"].astype(
                            bool))
                ) &
                (dataframe["volume"] > dataframe["prev_volume"])
        )
        cond_signal = cond_A_relaxed | cond_B

        ratio = np.where(dataframe["is_atr_rising"], atr_ratio_th + 0.1, atr_ratio_th)
        min_distance = min_dist * dataframe["atr"]
        threshold = dataframe["low_breakout"] + ratio * (dataframe["high_rebound"] - dataframe["low_breakout"])
        threshold = np.where(
            threshold < dataframe["low_breakout"] + min_distance,
            dataframe["low_breakout"] + min_distance,
            threshold,
        )

        cond_entry_price = dataframe["close"] < threshold
        cond_body = (
                (dataframe["body"] > body_low * dataframe["atr"]) &
                (dataframe["body"] < body_up * dataframe["atr"]) &
                (dataframe["close"] < dataframe["open"])
        )

        cond_volume_burst = dataframe["volume"] > (dataframe["prev_volume"] * vol_burst)
        cond_execution = cond_entry_price & cond_body
        if self.enable_volume_confirmation.value >= 0.5:
            cond_execution = cond_execution & cond_volume_burst

        cond_full = cond_env & cond_signal & cond_execution
        cond_basic_short = cond_trend_alignment & cond_A_relaxed

        dataframe["enter_short"] = ((cond_basic_short) | (cond_full)).astype(int)
        dataframe["dbg_env"] = cond_env.astype(int)
        dataframe["dbg_signal"] = cond_signal.astype(int)
        dataframe["dbg_exec"] = cond_execution.astype(int)
        dataframe["dbg_full"] = cond_full.astype(int)
        dataframe["dbg_basic"] = cond_basic_short.astype(int)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        amp_ratio = self.consolidation_amplitude_ratio.value
        vol_ratio = self.consolidation_volatility_ratio.value
        upper_shadow = self.upper_shadow_ratio.value
        vol_filter = self.volume_filter_ratio.value
        atr_ratio_th = self.atr_ratio_threshold.value
        min_dist = self.min_distance_ratio.value
        body_low = self.body_lower_ratio.value
        body_up = self.body_upper_ratio.value
        vol_burst = self.volume_burst_ratio.value

        cond_trend_alignment = (
                (dataframe["close"] < dataframe["ma7"]) &
                (dataframe["ma7"] < dataframe["ma25"]) &
                (dataframe["ma25"] < dataframe["ma99"]) &
                (dataframe["is_ma25_negative_slope"]) &
                (dataframe["is_ma99_negative_slope"])
        )

        cond_consolidation_raw = (
                (dataframe["consolidation_amplitude"] < amp_ratio) &
                (dataframe["consolidation_volatility"] < vol_ratio)
        )
        if self.enable_consolidation_filter.value < 0.5:
            cond_consolidation = pd.Series(True, index=dataframe.index)
        else:
            cond_consolidation = cond_consolidation_raw

        # Pre-drop: low10 or trendline, both with ATR buffer.
        buffer_atr = self.break_atr_buffer.value
        break_level_low10 = dataframe["low_10"] - buffer_atr * dataframe["atr"]

        use_trendline = self.break_mode.value >= 0.5
        trendline_ok = (dataframe["trendline_slope"] > 0) & pd.notna(dataframe["trendline_low"])
        break_level_trend = dataframe["trendline_low"] - buffer_atr * dataframe["atr"]
        break_level = np.where(use_trendline & trendline_ok, break_level_trend, break_level_low10)
        cond_pre_drop = dataframe["close"] < break_level

        cond_env = cond_trend_alignment & cond_consolidation & cond_pre_drop

        cond_A = (
                (dataframe["high"] > np.minimum(dataframe["ma7"], dataframe["ma25"])) &
                (dataframe["upper_shadow"] > upper_shadow * dataframe["atr"]) &
                (dataframe["volume"] < dataframe["volume_mean"] * vol_filter)
        )

        # Weak rebound (locked to ATR mode): close is near ma7 while below ma7.
        diff_ma7 = (dataframe["close"] - dataframe["ma7"]).abs()
        cond_weak_rebound = diff_ma7 <= (self.weak_rebound_atr.value * dataframe["atr"])
        cond_A_relaxed = cond_A | (cond_weak_rebound & (dataframe["close"] < dataframe["ma7"]))

        cond_B = (
                (
                        (dataframe["prev_close_above_ma7"].astype(bool) & dataframe["below_ma7"].astype(bool)) |
                        ((dataframe["close"].shift(2) < dataframe["ma7"].shift(2)) & dataframe["below_ma7"].astype(
                            bool)) |
                        ((dataframe["close"].shift(3) < dataframe["ma7"].shift(3)) & dataframe["below_ma7"].astype(
                            bool))
                ) &
                (dataframe["volume"] > dataframe["prev_volume"])
        )

        cond_signal = cond_A_relaxed | cond_B

        ratio = np.where(dataframe["is_atr_rising"], atr_ratio_th + 0.1, atr_ratio_th)
        min_distance = min_dist * dataframe["atr"]

        threshold = dataframe["low_breakout"] + ratio * (dataframe["high_rebound"] - dataframe["low_breakout"])
        threshold = np.where(
            threshold < dataframe["low_breakout"] + min_distance,
            dataframe["low_breakout"] + min_distance,
            threshold,
        )

        cond_entry_price = dataframe["close"] < threshold

        cond_body = (
                (dataframe["body"] > body_low * dataframe["atr"]) &
                (dataframe["body"] < body_up * dataframe["atr"]) &
                (dataframe["close"] < dataframe["open"])
        )

        cond_volume_burst = dataframe["volume"] > (dataframe["prev_volume"] * vol_burst)

        cond_execution = cond_entry_price & cond_body
        if self.enable_volume_confirmation.value >= 0.5:
            cond_execution = cond_execution & cond_volume_burst

        cond_full = cond_env & cond_signal & cond_execution
        cond_basic_short = cond_trend_alignment & cond_A_relaxed

        dataframe.loc[(cond_basic_short) | (cond_full), "enter_short"] = 1

        # Debug exports for signal review.
        dataframe["dbg_env"] = cond_env.astype(int)
        dataframe["dbg_signal"] = cond_signal.astype(int)
        dataframe["dbg_exec"] = cond_execution.astype(int)
        dataframe["dbg_full"] = cond_full.astype(int)
        dataframe["dbg_basic"] = cond_basic_short.astype(int)

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        # AMRS3.7: use custom_exit only for short exits.
        return dataframe

    def get_entry_price(self, pair: str, side: str, **kwargs) -> float:
        return None

    def confirm_trade_entry(
            self,
            pair: str,
            order_type: str,
            amount: float,
            rate: float,
            time_in_force: str,
            current_time: datetime,
            entry_tag: str,
            side: str,
            **kwargs,
    ) -> bool:
        return True

    def custom_stoploss(
            self,
            pair: str,
            trade: "Trade",
            current_time: datetime,
            current_rate: float,
            current_profit: float,
            **kwargs,
    ) -> float:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return -0.05

        current_candle = dataframe.iloc[-1]
        if trade.is_short:
            entry_price = trade.open_rate
            atr = current_candle["atr"]
            if pd.notna(current_candle["high_rebound"]):
                dynamic_sl = (current_candle["high_rebound"] + 1.2 * atr) / entry_price - 1
                dynamic_sl = max(dynamic_sl, 0.02)
                age_candles = 0
                if trade.open_date_utc:
                    age_minutes = max((current_time - trade.open_date_utc).total_seconds() / 60.0, 0.0)
                    age_candles = int(age_minutes // 15)

                if age_candles >= int(self.sl_tighten_after_candles.value):
                    dynamic_sl = min(dynamic_sl, float(self.sl_max_after_tighten.value))

                if current_profit >= float(self.sl_breakeven_profit.value):
                    dynamic_sl = min(dynamic_sl, max(0.0, -float(self.sl_breakeven_sl.value)))

                return -dynamic_sl

        return -0.05

    def custom_exit(
            self,
            pair: str,
            trade: "Trade",
            current_time: datetime,
            current_rate: float,
            current_profit: float,
            **kwargs,
    ) -> str:
        if not trade.is_short:
            return None

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return None

        current_candle = dataframe.iloc[-1]
        entry_price = trade.open_rate
        atr = current_candle["atr"]

        profit_target = self.atr_trailing_profit.value * atr / entry_price
        if current_profit >= profit_target:
            trailing_stop = self.atr_trailing_stop.value * atr / entry_price
            if current_profit >= trailing_stop:
                return "atr_trailing_exit"

        if current_candle["close"] > current_candle["ma25"] * float(self.ma25_offset_exit.value):
            return "ma25_takeprofit"

        age_candles = 0
        if trade.open_date_utc:
            age_minutes = max((current_time - trade.open_date_utc).total_seconds() / 60.0, 0.0)
            age_candles = int(age_minutes // 15)

        if (
                current_candle["close"] > current_candle["ma25"] * float(self.defense_ma25_offset.value)
                and current_profit <= float(self.defense_max_loss.value)
                and age_candles >= int(self.defense_min_age_candles.value)
        ):
            return "ma25_defense"

        return None
```
