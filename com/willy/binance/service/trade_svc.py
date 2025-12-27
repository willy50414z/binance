from datetime import datetime
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING

import numpy as np
import pandas as pd

from com.willy.binance.config.config_util import config_util
from com.willy.binance.config.const import DECIMAL_PLACE_2
from com.willy.binance.dto.binance_kline import BinanceKline
from com.willy.binance.dto.trade_detail import TradeDetail
from com.willy.binance.dto.trade_record import TradeRecord
from com.willy.binance.dto.txn_detail import TxnDetail
from com.willy.binance.enums.handle_fee_type import HandleFeeType
from com.willy.binance.enums.trade_reason import TradeReason, TradeReasonType
from com.willy.binance.enums.trade_type import TradeType


def calc_max_loss(highest_price: Decimal, lowest_price: Decimal, total_handle_amt: Decimal, total_handle_fee,
                  units: Decimal,
                  handle_fee_type=HandleFeeType.TAKER):
    if units > 0:
        return min(calc_profit(highest_price, total_handle_amt, total_handle_fee, units, handle_fee_type),
                   calc_profit(lowest_price, total_handle_amt, total_handle_fee, units, handle_fee_type))
    else:
        return Decimal("0")


def calc_profit(current_price: Decimal, total_handle_amt: Decimal, total_handle_fee, units: Decimal,
                handle_fee_type=HandleFeeType.TAKER):
    fee_rate = Decimal(str(config_util("binance.trade.handle.fee").get(handle_fee_type.name)))
    if units > 0:
        # 平倉多倉
        # (賣金 - 賣手續) - 買金 - 買手續
        profit = current_price * units * (1 - fee_rate) - total_handle_amt - total_handle_fee
        # profit + total_handling_amt + total_handling_fee  / units / (1 - fee_rate)
    elif units < 0:
        # 平倉空倉
        # 賣金 - 賣手續 - (買價 + 買手續)
        profit = (total_handle_amt - total_handle_fee) - current_price * -1 * units * (1 + fee_rate)
        # (total_handling_amt - total_handling_fee)- profit / -1 / units / (1 + fee_rate)
    else:
        return None
    return profit.quantize(DECIMAL_PLACE_2, ROUND_FLOOR)


def calc_force_close_offset_price(profit: Decimal, total_handle_amt: Decimal, total_handle_fee: Decimal, units: Decimal,
                                  handle_fee_type: HandleFeeType = HandleFeeType.TAKER):
    """
    Args:
        profit: 預期獲利
        total_handle_amt: 持倉金額
        total_handle_fee: 總手續費
        units: 持倉單位數
        handle_fee_type: 手續費類別

    Returns:

    """
    handle_fee_ratio = Decimal(str(config_util("binance.trade.handle.fee").get(handle_fee_type.name)))
    if units > 0:
        force_close_offset_price = (profit + total_handle_amt + total_handle_fee) / units / (1 - handle_fee_ratio)
    elif units < 0:
        force_close_offset_price = ((total_handle_amt - total_handle_fee) - profit) / -1 / units / (
                1 + handle_fee_ratio) - 1
    else:
        return None
    return force_close_offset_price.quantize(Decimal("1"), rounding=ROUND_CEILING)


def calc_buyable_units(invest_amt: Decimal, price: float) -> Decimal:
    """

    Args:
        invest_amt: 投資額
        price: 價格
        handle_fee_type: 手續費類別

    Returns:

    """
    if invest_amt is None or invest_amt <= Decimal("0"):
        return Decimal("0")
    return (invest_amt / Decimal(str(price))).quantize(Decimal("0.001"), rounding=ROUND_FLOOR)


def calc_handle_fee(price: Decimal, units: Decimal, handle_fee_type: HandleFeeType = HandleFeeType.TAKER
                    ) -> Decimal:
    handle_fee_ratio = Decimal(str(config_util("binance.trade.handle.fee").get(handle_fee_type.name)))
    return (price * units * handle_fee_ratio).quantize(DECIMAL_PLACE_2, rounding=ROUND_CEILING)


def calc_trade_amt(price: Decimal, units: Decimal) -> Decimal:
    return price * units


def create_trade_record(date: datetime, trade_type: TradeType, price: float, amt: Decimal = None,
                        unit: Decimal = None,
                        handle_fee_type: HandleFeeType = HandleFeeType.TAKER,
                        reason: TradeReason = "") -> TradeRecord | None:
    if (amt and unit) or (amt is None and unit is None):
        raise ValueError("amt and unit can't both not none")

    buyable_units = None
    if amt:
        buyable_units = calc_buyable_units(amt, price)
    if unit:
        buyable_units = unit

    if buyable_units and buyable_units > 0:
        return TradeRecord(date, trade_type, Decimal(str(price)), buyable_units, handle_fee_type, reason)
    else:
        return None


def create_close_trade_record(date: datetime, price: Decimal, txn_detail: TxnDetail,
                              handle_fee_type: HandleFeeType = HandleFeeType.TAKER,
                              reason: TradeReason = "") -> TradeRecord | None:
    amt = None
    unit = abs(txn_detail.units)
    trade_type = TradeType.BUY if txn_detail.units < 0 else TradeType.SELL
    return create_trade_record(date, trade_type, price, amt, unit, handle_fee_type, reason=reason)


def build_txn_detail_list_df(row, invest_amt: Decimal,
                             leverage_ratio: Decimal,
                             trade_record: TradeRecord | None, trade_detail: TradeDetail):
    if trade_record is None:
        return
    return build_txn_detail_list(
        BinanceKline(row.start_time, Decimal(str(row.open)), Decimal(str(row.high)), Decimal(str(row.low)),
                     Decimal(str(row.close)),
                     Decimal(str(row.vol)), row.end_time,
                     int(row.number_of_trade)), invest_amt, leverage_ratio,
        trade_record,
        trade_detail)


def build_txn_detail_list(binanceKline: BinanceKline, invest_amt: Decimal,
                          leverage: Decimal,
                          trade_record: TradeRecord | None, trade_detail: TradeDetail):
    """

    :param binanceKline:
    :param invest_amt: 投資金額(未被槓桿放大)
    leverage_ratio: 槓桿倍數
    trade_record: 新的一筆交易
    :param trade_detail:
    :return:
    """
    current_price = binanceKline.open
    current_date = binanceKline.start_time
    last_handle_units = Decimal("0")
    last_handle_amt = Decimal("0")
    last_handle_fee = Decimal("0")
    last_trade_detail_guarantee = Decimal("0")
    last_trade_detail_force_close_offset_price = Decimal("0")
    last_trade_detail_acct_balance = invest_amt
    last_trade_break_even_point_price = Decimal("0")
    last_trade_max_loss = Decimal("0")
    last_total_profit = Decimal("0")
    if len(trade_detail.txn_detail_list) > 0:
        last_trade_detail = trade_detail.txn_detail_list[len(trade_detail.txn_detail_list) - 1]
        last_handle_units = last_trade_detail.units
        last_handle_amt = last_trade_detail.handle_amt
        last_handle_fee = last_trade_detail.handling_fee
        last_trade_detail_guarantee = last_trade_detail.guarantee_fee
        last_trade_detail_force_close_offset_price = last_trade_detail.force_close_offset_price
        last_trade_detail_acct_balance = last_trade_detail.acct_balance
        last_trade_break_even_point_price = last_trade_detail.break_even_point_price
        last_trade_max_loss = last_trade_detail.max_loss
        last_total_profit = last_trade_detail.total_profit

    if trade_record is not None and trade_record.unit != 0:
        if trade_record.type == TradeType.BUY:
            total_handle_units = last_handle_units + trade_record.unit
            trade_amt = calc_trade_amt(trade_record.price, trade_record.unit)
            if last_handle_units >= 0:
                total_handle_amt = last_handle_amt + trade_amt
                total_handle_fee = last_handle_fee + calc_handle_fee(trade_record.price, trade_record.unit,
                                                                     trade_record.handle_fee_type)
                profit = Decimal("0")
                profit_ratio = Decimal("0")
            else:
                # 賣轉買
                if trade_record.unit > abs(last_handle_units):
                    # 買入單位>之前持有的空倉單位
                    remain_unit = (trade_record.unit + last_handle_units)
                    total_handle_amt = calc_trade_amt(trade_record.price, remain_unit)
                    total_handle_fee = calc_handle_fee(trade_record.price, remain_unit, trade_record.handle_fee_type)
                    sell_amt = last_handle_amt - last_handle_fee
                    buy_amt = trade_record.price * last_handle_units * -1 + calc_handle_fee(trade_record.price,
                                                                                            last_handle_units * -1,
                                                                                            trade_record.handle_fee_type)
                    profit = (sell_amt - buy_amt).quantize(DECIMAL_PLACE_2, ROUND_FLOOR)
                    # profit = calc_profit(trade_record.price, last_handle_amt, last_handle_fee, last_handle_units,
                    #                      trade_record.handle_fee_type)
                else:
                    # 買入部分<放空艙位
                    total_handle_amt = last_handle_amt / last_handle_units * total_handle_units
                    total_handle_fee = last_handle_fee / last_handle_units * total_handle_units
                    sell_amt = last_handle_amt - total_handle_amt - last_handle_fee - total_handle_fee
                    handle_fee = calc_handle_fee(trade_record.price, trade_record.unit, trade_record.handle_fee_type)
                    buy_amt = trade_record.price * trade_record.unit + handle_fee
                    profit = (sell_amt - buy_amt).quantize(DECIMAL_PLACE_2, ROUND_FLOOR)
                    # profit = calc_profit(trade_record.price,
                    #                      -1 * (last_handle_amt / last_handle_units * trade_record.unit),
                    #                      last_handle_fee - total_handle_fee, -1 * trade_record.unit,
                    #                      trade_record.handle_fee_type)
                profit_ratio = profit / sell_amt / leverage

            total_profit = last_total_profit + profit
            stock_cost = (total_handle_amt / leverage + total_handle_fee).quantize(DECIMAL_PLACE_2, ROUND_CEILING)
            # 總投資額+累計獲利-庫存成本
            acct_balance = invest_amt + total_profit - stock_cost
            guarantee = (total_handle_amt / leverage).quantize(DECIMAL_PLACE_2, rounding=ROUND_CEILING)
            max_loss = calc_max_loss(binanceKline.high, binanceKline.low, total_handle_amt, total_handle_fee,
                                     total_handle_units,
                                     HandleFeeType.TAKER)

            force_close_offset_price = calc_force_close_offset_price(-1 * invest_amt,
                                                                     total_handle_amt,
                                                                     total_handle_fee,
                                                                     total_handle_units,
                                                                     HandleFeeType.TAKER)
            break_even_point_price = calc_force_close_offset_price(Decimal("0"),
                                                                   total_handle_amt, total_handle_fee,
                                                                   total_handle_units)

            trade_detail.txn_detail_list.append(
                TxnDetail(current_date, total_handle_units, total_handle_amt, total_handle_fee,
                          guarantee,
                          trade_record.price, profit, profit_ratio, total_profit,
                          force_close_offset_price,
                          break_even_point_price,
                          max_loss,
                          acct_balance,
                          trade_record))
        elif trade_record.type == TradeType.SELL:
            total_handle_units = last_handle_units - trade_record.unit
            trade_amt = calc_trade_amt(trade_record.price, trade_record.unit)

            if last_handle_units <= 0:
                total_handle_amt = last_handle_amt + trade_amt
                total_handle_fee = last_handle_fee + calc_handle_fee(trade_record.price, trade_record.unit,
                                                                     trade_record.handle_fee_type)
                profit = Decimal("0")
                profit_ratio = Decimal("0")
            else:
                # 買轉賣
                if trade_record.unit > abs(last_handle_units):
                    # 買入單位>之前持有的空倉單位
                    remain_unit = (trade_record.unit * -1 + last_handle_units)
                    total_handle_amt = abs(calc_trade_amt(trade_record.price, remain_unit))
                    total_handle_fee = abs(
                        calc_handle_fee(trade_record.price, remain_unit, trade_record.handle_fee_type))
                    sell_amt = last_handle_units * trade_record.price - calc_handle_fee(trade_record.price,
                                                                                        last_handle_units,
                                                                                        trade_record.handle_fee_type)
                    buy_amt = last_handle_amt + last_handle_fee
                    profit = (sell_amt - buy_amt).quantize(DECIMAL_PLACE_2, ROUND_FLOOR)
                    # profit = calc_profit(trade_record.price, last_handle_amt, last_handle_fee, last_handle_units,
                    #                      trade_record.handle_fee_type)
                else:
                    # 買入單位<之前持有的空倉單位
                    total_handle_amt = last_handle_amt / last_handle_units * total_handle_units
                    total_handle_fee = last_handle_fee / last_handle_units * total_handle_units
                    buy_amt = last_handle_amt - total_handle_amt + last_handle_fee - total_handle_fee
                    handle_fee = calc_handle_fee(trade_record.price, trade_record.unit, trade_record.handle_fee_type)
                    sell_amt = trade_record.price * trade_record.unit - handle_fee
                    profit = (sell_amt - buy_amt).quantize(DECIMAL_PLACE_2, ROUND_FLOOR)
                    # profit = calc_profit(trade_record.price, last_handle_amt / last_handle_units * trade_record.unit,
                    #                      calc_handle_fee(last_handle_amt / last_handle_units, trade_record.unit,
                    #                                      trade_record.handle_fee_type), trade_record.unit,
                    #                      trade_record.handle_fee_type)
                profit_ratio = profit / buy_amt / leverage

            total_profit = last_total_profit + profit
            stock_cost = (total_handle_amt / leverage + total_handle_fee).quantize(DECIMAL_PLACE_2, ROUND_CEILING)
            # 總投資額+累計獲利-庫存成本
            acct_balance = invest_amt + total_profit - stock_cost

            guarantee = (total_handle_amt / leverage).quantize(DECIMAL_PLACE_2, rounding=ROUND_CEILING)
            max_loss = calc_max_loss(binanceKline.high, binanceKline.low, total_handle_amt, total_handle_fee,
                                     total_handle_units,
                                     HandleFeeType.TAKER)
            force_close_offset_price = calc_force_close_offset_price(-1 * invest_amt,
                                                                     total_handle_amt,
                                                                     total_handle_fee,
                                                                     total_handle_units,
                                                                     HandleFeeType.TAKER)
            break_even_point_price = calc_force_close_offset_price(Decimal("0"),
                                                                   total_handle_amt, total_handle_fee,
                                                                   total_handle_units)
            trade_detail.txn_detail_list.append(
                TxnDetail(current_date, total_handle_units, total_handle_amt, total_handle_fee,
                          guarantee,
                          trade_record.price, profit, profit_ratio, last_total_profit + profit,
                          force_close_offset_price,
                          break_even_point_price,
                          max_loss,
                          acct_balance,
                          trade_record))
    else:
        profit = calc_profit(current_price, last_handle_amt, last_handle_fee, last_handle_units,
                             HandleFeeType.TAKER)

        profit_ratio = None
        if profit and last_handle_amt:
            profit_ratio = profit / last_handle_amt / leverage

        trade_detail.txn_detail_list.append(
            TxnDetail(current_date, last_handle_units, last_handle_amt, last_handle_fee,
                      last_trade_detail_guarantee,
                      current_price, profit, profit_ratio, last_total_profit + profit,
                      last_trade_detail_force_close_offset_price,
                      last_trade_break_even_point_price, last_trade_max_loss, last_trade_detail_acct_balance,
                      trade_record))


# TODO is function need to check
def check_is_force_close_offset(kline: BinanceKline, invest_amt: Decimal,
                                leverage_ratio: Decimal, trade_detail: TradeDetail):
    # 確認是否爆倉
    latest_txn_detail = trade_detail.txn_detail_list[len(trade_detail.txn_detail_list) - 1]
    # 是否做多
    is_long_trade = latest_txn_detail.units > 0
    # if (latest_txn_detail.force_close_offset_price
    #         and ((is_long_trade and kline.low < latest_txn_detail.force_close_offset_price)
    #              or (not is_long_trade and kline.high > latest_txn_detail.force_close_offset_price))):
    if (is_long_trade and kline.low < latest_txn_detail.force_close_offset_price) or (
            not is_long_trade and kline.high > latest_txn_detail.force_close_offset_price):
        trade_detail.txn_detail_list.append(
            TxnDetail(kline.end_time, Decimal("0"), Decimal("0"), Decimal("0"),
                      Decimal("0"),
                      latest_txn_detail.force_close_offset_price, -1 * invest_amt,
                      Decimal(-100 * leverage_ratio), Decimal("0"),
                      Decimal("0"), -1 * invest_amt, Decimal("0"), Decimal("0"),
                      TradeRecord(kline.end_time, TradeType.SELL if is_long_trade else TradeType.BUY,
                                  latest_txn_detail.force_close_offset_price,
                                  -1 * latest_txn_detail.units,
                                  HandleFeeType.TAKER, TradeReason(TradeReasonType.PASSIVE, "爆倉"))))
        return True


def analyze_trading_strategy(df: pd.DataFrame, initial_capital: float, risk_free_rate: float = 0.02) -> pd.DataFrame:
    """
    分析交易策略的績效指標。

    Args:
        df: 交易紀錄 DataFrame，包含 date, profit, total_profit 等欄位。
        initial_capital: 策略的初始資金。
        risk_free_rate: 年化無風險利率 (預設 2%)。

    Returns:
        包含統計數據的 DataFrame。
    """

    # --- 1. 數據準備與淨值曲線計算 ---
    df = df.copy()

    # 確保 date 是 datetime 類型且排序
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(by='date').reset_index(drop=True)

    # 計算淨值曲線 (Equity Curve)
    df['equity'] = initial_capital + df['total_profit']

    # 策略運行的總日數 (用於年化計算)
    if len(df) > 1:
        total_days = (df['date'].iloc[-1] - df['date'].iloc[0]).days
    else:
        total_days = 1  # 避免除以零

    years = total_days / 365.25 if total_days > 0 else 1

    # 計算每日或每次操作的報酬率
    # 這裡使用淨值的變化率作為報酬率
    df['returns'] = df['equity'].ffill().pct_change().fillna(0)

    # --- 2. 報酬指標 (Return Metrics) ---
    # 1. 安全取得最終淨值
    final_equity = float(df['equity'].iloc[-1]) if not df.empty else initial_capital

    # 計算總報酬率
    total_return = (final_equity - initial_capital) / initial_capital

    # 2. 計算回測天數與年化係數 (針對 15分鐘線)
    # 取得資料筆數
    num_bars = len(df)
    # 15分鐘線一年的總量 (365天 * 24小時 * 4)
    bars_per_year = 35040
    years = num_bars / bars_per_year

    # 3. 計算 CAGR (加入保護機制)
    if years > 0 and final_equity > 0:
        # 使用實數計算，避免產生複數
        cagr = (pow(final_equity / initial_capital, 1 / years) - 1)
    else:
        # 如果虧損到 0 以下，CAGR 定義為 -100%
        cagr = -1.0 if final_equity <= 0 else 0.0

    # 4. 計算波動度 (Volatility) - 需與 15M 頻率對齊
    # 假設 df['return'] 是每 15 分鐘的報酬率
    log_return = np.log(df['equity'] / df['equity'].shift(1))
    volatility = log_return.std() * np.sqrt(bars_per_year)

    # 5. 計算夏普比率 (假設無風險利率 0)
    sharpe_ratio = (cagr / volatility) if volatility != 0 else 0

    # 獲利因子 (Profit Factor)
    winning_trades = df[df['profit'] > 0]['profit'].sum()
    losing_trades = df[df['profit'] < 0]['profit'].sum()
    profit_factor = winning_trades / abs(losing_trades) if losing_trades != 0 else np.inf

    # --- 3. 風險指標 (Risk Metrics) ---

    # 最大回檔 (Max Drawdown, MDD)
    df['peak'] = df['equity'].cummax()
    df['drawdown'] = (df['equity'] / df['peak']) - 1
    max_drawdown = round(df['drawdown'].min(), 2)

    # 年化波動度 (Volatility)
    # 這裡使用操作報酬率的標準差，並年化 (假設每天一次操作，如果頻率不同需調整)
    # 更標準的做法是使用日頻率的報酬，但這裡我們根據現有數據計算
    annual_volatility = df['returns'].astype(float).std() * np.sqrt(252)  # 假設一年252個交易日

    # --- 4. 交易特性指標 (Trade Metrics) ---

    # 總交易筆數 (假設 profit 不為 0 算一筆平倉交易)
    total_trades = df[df['profit'] != 0].shape[0]

    # 勝率 (Win Rate)
    winning_trades_count = df[df['profit'] > 0].shape[0]
    win_rate = winning_trades_count / total_trades if total_trades > 0 else 0

    # 平均獲利/虧損
    avg_win = df[df['profit'] > 0]['profit'].mean()
    avg_loss = df[df['profit'] < 0]['profit'].mean()

    # 最大連續虧損次數 (Max Consecutive Losses)
    loss_series = (df['profit'] < 0).astype(int)
    max_consecutive_losses = 0
    current_consecutive_losses = 0
    for is_loss in loss_series:
        if is_loss:
            current_consecutive_losses += 1
        else:
            max_consecutive_losses = max(max_consecutive_losses, current_consecutive_losses)
            current_consecutive_losses = 0
    max_consecutive_losses = max(max_consecutive_losses, current_consecutive_losses)  # 考慮最後一波連虧

    # --- 5. 整理輸出結果 ---
    results = {
        '總結期間 (天)': total_days,
        '總交易筆數': total_trades,

        # 報酬指標
        '總報酬率 (%)': round(total_return * 100, 2),
        '年化報酬率 CAGR (%)': round(cagr * 100, 2),
        '獲利因子': round(profit_factor, 2),

        # 風險指標
        '最大回檔 MDD (%)': abs(max_drawdown) * 100,
        '年化波動度 (%)': annual_volatility * 100,
        '夏普比率': sharpe_ratio,

        # 交易特性指標
        '勝率 (%)': round(win_rate * 100, 2),
        '平均獲利金額': round(avg_win, 2),
        '平均虧損金額 (絕對值)': round(abs(avg_loss), 2),
        '最大連續虧損次數': max_consecutive_losses,
        '平均賺賠比': round(abs(avg_win / avg_loss) if avg_loss != 0 else np.inf, 2),
    }

    # 將結果轉換為 DataFrame
    results_series = pd.Series(results)

    # 2. 轉換為 2 列 N 欄的 DataFrame (轉置)
    # .to_frame(): 將 Series 轉為一列多行的 DataFrame
    # .T (Transpose): 將 DataFrame 轉置為 N 列一行 (符合您的要求)
    results_df_horizontal = results_series.to_frame().T

    return results_df_horizontal


if __name__ == '__main__':
    base_kline = BinanceKline(
        start_time=datetime(2025, 1, 1, 0, 0),
        open=Decimal("50000"),
        high=Decimal("51000"),
        low=Decimal("49000"),
        close=Decimal("50500"),
        vol=Decimal("1"),
        end_time=datetime(2025, 1, 1, 0, 14, 59),
        number_of_trade=100
    )
    invest_amt = Decimal("10000")
    leverage = Decimal("10")

    td = TradeDetail([])
    trade_record = create_trade_record(datetime(2025, 1, 1, 0, 0), TradeType.BUY, Decimal("50000"), None,
                                       Decimal("0.2"),
                                       HandleFeeType.TAKER, TradeReason(TradeReasonType.ACTIVE, ""))
    build_txn_detail_list(base_kline, invest_amt, leverage, trade_record, td)

    trade_record = create_trade_record(datetime(2025, 1, 1, 0, 0), TradeType.BUY, Decimal("52000"), None,
                                       Decimal("0.1"),
                                       HandleFeeType.MAKER, TradeReason(TradeReasonType.ACTIVE, ""))
    build_txn_detail_list(base_kline, invest_amt, leverage, trade_record, td)

    trade_record = create_trade_record(datetime(2025, 1, 1, 0, 0), TradeType.SELL, Decimal("53000"), None,
                                       Decimal("0.1"),
                                       HandleFeeType.TAKER, TradeReason(TradeReasonType.ACTIVE, ""))
    build_txn_detail_list(base_kline, invest_amt, leverage, trade_record, td)

    trade_record = create_trade_record(datetime(2025, 1, 1, 0, 0), TradeType.SELL, Decimal("52000"), None,
                                       Decimal("0.4"),
                                       HandleFeeType.TAKER, TradeReason(TradeReasonType.ACTIVE, ""))
    build_txn_detail_list(base_kline, invest_amt, leverage, trade_record, td)

    trade_record = create_trade_record(datetime(2025, 1, 1, 0, 0), TradeType.SELL, Decimal("51000"), None,
                                       Decimal("0.1"),
                                       HandleFeeType.MAKER, TradeReason(TradeReasonType.ACTIVE, ""))
    build_txn_detail_list(base_kline, invest_amt, leverage, trade_record, td)

    trade_record = create_trade_record(datetime(2025, 1, 1, 0, 0), TradeType.BUY, Decimal("49000"), None,
                                       Decimal("0.1"),
                                       HandleFeeType.TAKER, TradeReason(TradeReasonType.ACTIVE, ""))
    build_txn_detail_list(base_kline, invest_amt, leverage, trade_record, td)

    trade_record = create_trade_record(datetime(2025, 1, 1, 0, 0), TradeType.BUY, Decimal("50000"), None,
                                       Decimal("0.4"),
                                       HandleFeeType.TAKER, TradeReason(TradeReasonType.ACTIVE, ""))
    build_txn_detail_list(base_kline, invest_amt, leverage, trade_record, td)

    trade_record = create_trade_record(datetime(2025, 1, 1, 0, 0), TradeType.SELL, Decimal("51000"), None,
                                       Decimal("0.2"),
                                       HandleFeeType.TAKER, TradeReason(TradeReasonType.ACTIVE, ""))
    build_txn_detail_list(base_kline, invest_amt, leverage, trade_record, td)

    result_list = [TxnDetail(date=datetime(2025, 1, 1, 0, 0), units=Decimal('0.2'), handle_amt=Decimal('10000.0'),
                             handling_fee=Decimal('4.00'), guarantee_fee=Decimal('1000.00'),
                             current_price=Decimal('50000'), profit=Decimal('0'), profit_ratio=Decimal('0'),
                             total_profit=Decimal('0'), force_close_offset_price=Decimal('21'),
                             break_even_point_price=Decimal('50041'), max_loss=Decimal('-207.92'),
                             acct_balance=Decimal('8996.00'),
                             trade_record=TradeRecord(date=datetime(2025, 1, 1, 0, 0),
                                                      type=TradeType.BUY, price=Decimal('50000'), unit=Decimal('0.2'),
                                                      handle_fee_type=HandleFeeType.TAKER,
                                                      reason=TradeReason(trade_reason_type=TradeReasonType.ACTIVE,
                                                                         desc='')))
        , TxnDetail(date=datetime(2025, 1, 1, 0, 0), units=Decimal('0.3'), handle_amt=Decimal('15200.0'),
                    handling_fee=Decimal('5.04'), guarantee_fee=Decimal('1520.00'), current_price=Decimal('52000'),
                    profit=Decimal('0'), profit_ratio=Decimal('0'), total_profit=Decimal('0'),
                    force_close_offset_price=Decimal('17358'), break_even_point_price=Decimal('50704'),
                    max_loss=Decimal('-510.92'), acct_balance=Decimal('8474.96'),
                    trade_record=TradeRecord(date=datetime(2025, 1, 1, 0, 0), type=TradeType.BUY,
                                             price=Decimal('52000'), unit=Decimal('0.1'),
                                             handle_fee_type=HandleFeeType.MAKER,
                                             reason=TradeReason(trade_reason_type=TradeReasonType.ACTIVE, desc='')))
        , TxnDetail(date=datetime(2025, 1, 1, 0, 0), units=Decimal('0.2'),
                    handle_amt=Decimal('10133.33333333333333333333333'), handling_fee=Decimal('3.36'),
                    guarantee_fee=Decimal('1013.34'), current_price=Decimal('53000'), profit=Decimal('229.53'),
                    profit_ratio=Decimal('0.004528695748251895424148834857'), total_profit=Decimal('229.53'),
                    force_close_offset_price=Decimal('684'), break_even_point_price=Decimal('50704'),
                    max_loss=Decimal('-340.62'), acct_balance=Decimal('9212.83'),
                    trade_record=TradeRecord(date=datetime(2025, 1, 1, 0, 0), type=TradeType.SELL,
                                             price=Decimal('53000'), unit=Decimal('0.1'),
                                             handle_fee_type=HandleFeeType.TAKER,
                                             reason=TradeReason(trade_reason_type=TradeReasonType.ACTIVE, desc='')))
        , TxnDetail(date=datetime(2025, 1, 1, 0, 0), units=Decimal('-0.2'), handle_amt=Decimal('10400.0'),
                    handling_fee=Decimal('4.16'), guarantee_fee=Decimal('1040.00'), current_price=Decimal('52000'),
                    profit=Decimal('259.14'), profit_ratio=Decimal('0.002556454964932680216559772287'),
                    total_profit=Decimal('488.67'), force_close_offset_price=Decimal('101938'),
                    break_even_point_price=Decimal('51958'), max_loss=Decimal('0'), acct_balance=Decimal('9444.51'),
                    trade_record=TradeRecord(date=datetime(2025, 1, 1, 0, 0), type=TradeType.SELL,
                                             price=Decimal('52000'), unit=Decimal('0.4'),
                                             handle_fee_type=HandleFeeType.TAKER,
                                             reason=TradeReason(trade_reason_type=TradeReasonType.ACTIVE, desc='')))
        , TxnDetail(date=datetime(2025, 1, 1, 0, 0), units=Decimal('-0.3'), handle_amt=Decimal('15500.0'),
                    handling_fee=Decimal('5.18'), guarantee_fee=Decimal('1550.00'), current_price=Decimal('51000'),
                    profit=Decimal('0'), profit_ratio=Decimal('0'), total_profit=Decimal('488.67'),
                    force_close_offset_price=Decimal('84948'), break_even_point_price=Decimal('51628'),
                    max_loss=Decimal('0'), acct_balance=Decimal('8933.49'),
                    trade_record=TradeRecord(date=datetime(2025, 1, 1, 0, 0), type=TradeType.SELL,
                                             price=Decimal('51000'), unit=Decimal('0.1'),
                                             handle_fee_type=HandleFeeType.MAKER,
                                             reason=TradeReason(trade_reason_type=TradeReasonType.ACTIVE, desc='')))
        , TxnDetail(date=datetime(2025, 1, 1, 0, 0), units=Decimal('-0.2'),
                    handle_amt=Decimal('10333.33333333333333333333333'),
                    handling_fee=Decimal('3.453333333333333333333333334'), guarantee_fee=Decimal('1033.34'),
                    current_price=Decimal('49000'), profit=Decimal('256.07'),
                    profit_ratio=Decimal('0.004964489049443909500390975885'), total_profit=Decimal('744.74'),
                    force_close_offset_price=Decimal('101608'), break_even_point_price=Decimal('51628'),
                    max_loss=Decimal('0'), acct_balance=Decimal('9707.95'),
                    trade_record=TradeRecord(date=datetime(2025, 1, 1, 0, 0), type=TradeType.BUY,
                                             price=Decimal('49000'), unit=Decimal('0.1'),
                                             handle_fee_type=HandleFeeType.TAKER,
                                             reason=TradeReason(trade_reason_type=TradeReasonType.ACTIVE, desc='')))
        , TxnDetail(date=datetime(2025, 1, 1, 0, 0), units=Decimal('0.2'), handle_amt=Decimal('10000.0'),
                    handling_fee=Decimal('4.00'), guarantee_fee=Decimal('1000.00'), current_price=Decimal('50000'),
                    profit=Decimal('325.88'), profit_ratio=Decimal('0.003154731710339326303887363648'),
                    total_profit=Decimal('1070.62'), force_close_offset_price=Decimal('21'),
                    break_even_point_price=Decimal('50041'), max_loss=Decimal('-207.92'),
                    acct_balance=Decimal('10066.62'),
                    trade_record=TradeRecord(date=datetime(2025, 1, 1, 0, 0), type=TradeType.BUY,
                                             price=Decimal('50000'), unit=Decimal('0.4'),
                                             handle_fee_type=HandleFeeType.TAKER,
                                             reason=TradeReason(trade_reason_type=TradeReasonType.ACTIVE, desc='')))
        , TxnDetail(date=datetime(2025, 1, 1, 0, 0), units=Decimal('0.0'), handle_amt=Decimal('0.0'),
                    handling_fee=Decimal('0.00'), guarantee_fee=Decimal('0.00'), current_price=Decimal('51000'),
                    profit=Decimal('191.92'), profit_ratio=Decimal('0.00191843262694922031187524990'),
                    total_profit=Decimal('1262.54'), force_close_offset_price=None, break_even_point_price=None,
                    max_loss=Decimal('0'), acct_balance=Decimal('11262.54'),
                    trade_record=TradeRecord(date=datetime(2025, 1, 1, 0, 0), type=TradeType.SELL,
                                             price=Decimal('51000'), unit=Decimal('0.2'),
                                             handle_fee_type=HandleFeeType.TAKER,
                                             reason=TradeReason(trade_reason_type=TradeReasonType.ACTIVE, desc='')))
                   ]

    print(result_list[0] == td.txn_detail_list[0])
    print(result_list[0])
    print(td.txn_detail_list[0])
