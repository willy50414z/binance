import logging
from datetime import datetime
# 引入 Decimal 以保證金額運算的精確度
from decimal import Decimal
from typing import List, Type

from binance import Client
from pandas import DataFrame

from com.willy.binance.dto.trade_record import TradeRecord
from com.willy.binance.enums.handle_fee_type import HandleFeeType
from com.willy.binance.enums.tech_idx_type import TechIdxType
from com.willy.binance.enums.trade_reason import TradeReason, TradeReasonType
from com.willy.binance.enums.trade_type import TradeType
from com.willy.binance.service import trade_svc
from com.willy.binance.strategy.trade_strategy import TradingStrategy, IndexSwitch


# 檢查是否發生連續同向交易
# 如果上一次交易與本次交易方向相同（例如：多 -> 多），則視為風險，選擇平倉
def trade_if_not_trade_twice(now_trade_record, last_td):
    if now_trade_record:
        # 如果上一次有交易紀錄，且方向相同，且尚未完全平倉
        if last_td is not None and last_td.trade_record.type == now_trade_record.type and last_td.units != 0:
            logging.debug("[strategy]meet trade_twice at same side, will stop trading")
            # 上一次是同向交易 => 直接平倉 因為同向交易發生時，大多會虧損
            # 建立平倉交易紀錄
            return trade_svc.create_close_trade_record(now_trade_record.date,
                                                       now_trade_record.price, last_td,
                                                       reason=TradeReason(
                                                           TradeReasonType.PASSIVE,
                                                           "同向交易攤平"))

    return now_trade_record


class Ma725BreakIndexSwitch(IndexSwitch):
    RSI = 1
    # ADX = 2
    ATR = 3
    KEEP = 4
    FAKE_BREAK = 5
    TIME_FILTER = 6
    # FAKE_BREAK_EARN = 6
    # FAKE_BREAK_RSI = 7


class Ma725BreakStrategy(TradingStrategy):
    def is_meet_tech_idx_with_switch(self, row) -> bool:
        """
        根據啟用的技術指標開關 (Switch) 檢查當前市場狀態是否符合進場條件。
        若任一啟用的檢查回傳 False，則不進行交易。
        """
        # 1. 檢查 MA25 趨勢方向
        # 若做 MA7 < MA25 (看跌)，但 MA25 仍在上升 (KEEP_GROW)，則過濾掉
        if self.get_trade_index_switch_status(Ma725BreakIndexSwitch.KEEP):
            if row.ma7 < row.ma25 and row.is_ma25_keep_grow:
                logging.debug(f"[is_meet_tech_idx_with_switch] fail in KEEP grow")
                return False
            # 若做 MA7 > MA25 (看漲)，但 MA25 仍在下降 (KEEP_FALL)，則過濾掉
            if row.ma7 > row.ma25 and row.is_ma25_keep_fall:
                logging.debug(f"[is_meet_tech_idx_with_switch] fail in KEEP fall")
                return False

        # 2. RSI 濾網
        # 若 RSI 過低 (趨勢過弱或超賣)，可能不適合追高/追空? 這裡邏輯似乎是過濾多頭訊號?
        # 原代碼：MA7 > MA25 (多頭訊號) 且 RSI < 60，則過濾 (要求強勢多頭才進場)
        if self.get_trade_index_switch_status(Ma725BreakIndexSwitch.RSI):
            # if row.ma7 < row.ma25 and row.rsi < 30:
            #     return False
            if row.ma7 > row.ma25 and row.rsi < 60:
                logging.debug(f"[is_meet_tech_idx_with_switch] fail in rsi fall")
                return False

            # ADX 過濾：開關打開且趨勢太弱 (ADX < 25) 時攔截
        # if self.get_trade_index_switch_status(MaIndexSwitch.ADX):
        #     if row.adx < 25:
        #         return False

        # 3. ATR 波動率過濾
        # 若當前 ATR 小於平均 ATR 的 80%，代表波動過小，不適合突破策略
        if self.get_trade_index_switch_status(Ma725BreakIndexSwitch.ATR):
            if row.atr < (row.atr_mean * 0.8):
                logging.debug(f"[is_meet_tech_idx_with_switch] fail in ATR")
                return False

        # 4. 時間過濾
        # 避免在特定時段 (如流動性差或劇烈波動時段) 交易
        if self.get_trade_index_switch_status(Ma725BreakIndexSwitch.TIME_FILTER):
            logging.debug(f"[is_meet_tech_idx_with_switch] fail in TIME_FILTER")
            return self.is_trade_allowed_time(row.end_time)

        logging.debug(f"[is_meet_tech_idx_with_switch] check success")
        return True

    @property
    def lookback_ticks(self) -> int:
        return 100

    @property
    def tickets_interval(self) -> str:
        return Client.KLINE_INTERVAL_15MINUTE

    @property
    def tech_idx_list(self) -> List[TechIdxType]:
        return [TechIdxType.SMA_7, TechIdxType.SMA_25, TechIdxType.IS_MA25_KEEP_GROW,
                TechIdxType.IS_MA25_KEEP_FALL, TechIdxType.MA7_AND_MA25_REL, TechIdxType.ADX_14, TechIdxType.ATR_14,
                TechIdxType.RSI_14]

    @property
    def strategy_idx_switches(self) -> Type[IndexSwitch]:
        return Ma725BreakIndexSwitch

    def get_invest_amt(self):
        if self.last_td is not None and self.last_td.acct_balance > 0:
            return self.last_td.acct_balance * Decimal("0.1") * self.leverage
        else:
            return self.initial_capital * Decimal("0.1") * self.leverage

    def get_trade_record_by_date(self, df: DataFrame) -> None | TradeRecord:
        """
        核心交易決策方法。
        傳入的 dataframe (df) 包含截止至目前決策點的歷史資料。
        回傳 TradeRecord 物件若決定進行交易，否則回傳 None。
        """
        # 取出最新的一筆資料 (當下決策點)
        lastest_row = df.iloc[-1]

        # 1. 冷靜期檢查：若剛發生過虧損或特定條件，暫停交易一段時間
        if self.is_in_cool_down_period(lastest_row.start_time):
            logging.info(f"[testResult]in_cool_down_period cool down~~")
            return

        # 2. 停損檢查：檢查持倉是否觸發停損條件 (例如虧損超過 1000 點)
        trade_record = self.get_stop_loss_trade_record(self.last_td, lastest_row)
        if trade_record:
            logging.debug("[strategy] trade in stop_loss_trade")
            return trade_record

        # 2. 策略進場檢查：檢查是否符合 MA 交叉策略 (趨勢突破)
        # 注意：這裡會優先於停損檢查執行。若符合反向訊號，會直接反手 (平倉並開新倉)。
        trade_record = self.trade_if_cross_ma(self.last_td, lastest_row)
        if trade_record:
            logging.debug("[strategy] trade in trade_if_cross_ma")
            return trade_record

        # 4. 假突破/假跌破檢查：若開啟此功能，檢查是否發生剛進場就被反向拉回的情況
        if self.get_trade_index_switch_status(Ma725BreakIndexSwitch.FAKE_BREAK):
            trade_record = self.fake_break(lastest_row)
            if trade_record:
                logging.debug("[strategy] trade in fake_break")
                return trade_record

        return None

    def is_trade_allowed_time(self, current_time: datetime) -> bool:
        """
        時間過濾器：過濾掉特定時段的交易訊號 (例如流動性差或波動劇烈時段)。
        目前設定：禁止 22:00 到 01:00 (UTC 時間需注意轉換) 之間的交易。
        """
        # 取得小時與分鐘
        hour = current_time.hour
        minute = current_time.minute

        # 舉例：禁止 22:00 ~ 01:00 (包含 22:15, 00:45)
        # 注意：這裡的時間通常是 UTC，請根據你的 K 線時區調整
        forbidden_hours = [22, 23, 0]

        if hour in forbidden_hours:
            return False

        return True

    def trade_if_cross_ma(self, last_td, row):
        """
        檢查是否符合 MA 交叉策略。
        邏輯：
        1. 確認 MA7 與 MA25 維持同向趨勢超過 20 期 (ma7_and_ma25_rel_criteria)。
        2. 若趨勢改變 (交叉)，且符合其他技術指標 (is_meet_tech_idx_with_switch)，則建立反向部位。
        """
        # 1. MA7 / MA25 超過20期沒有交叉 > 交叉後確立做多/空方向
        ma7_and_ma25_rel_criteria = 20

        # 檢查是否長期趨勢 (維持 20 期以上)
        if abs(row.last_ma7_and_ma25_rel) >= ma7_and_ma25_rel_criteria:
            # 情況 A: 之前 MA7 > MA25 (多頭趨勢) 持續超過 20 期
            if row.last_ma7_and_ma25_rel > 0:
                # ma7在ma25上面持續超過20期
                # 訊號：當前 MA7 跌破 MA25 (看空)，且通過指標過濾
                if row.ma7 < row.ma25 and self.is_meet_tech_idx_with_switch(row):
                    # ma7如果跌破ma25的時候賣
                    # # 如果之前做空，現在也做空，價差至少要>1000
                    # if last_td and last_td.trade_record.type == TradeType.SELL and abs(
                    #         last_td.trade_record.price - Decimal(row.ma7)) < 1000:
                    #     continue

                    # 計算倉位：如果之前是做多，現在要改做空，所以sell amt要包含之前做多的一起平掉 (翻空)
                    if last_td is not None:
                        handle_unit = last_td.units
                    else:
                        handle_unit = Decimal("0")

                    trade_amt = self.get_invest_amt()
                    # 若之前有多單 (handle_unit > 0)，則平倉量為 handle_unit
                    acct_handle_unit = handle_unit if handle_unit > 0 else Decimal("0")
                    trade_type = TradeType.SELL

                    # 新開倉位 + 平掉舊倉位
                    unit = trade_svc.calc_buyable_units(trade_amt, row.close) + acct_handle_unit
                    now_trade_record = trade_svc.create_trade_record(row.start_time, trade_type, row.close,
                                                                     unit=unit, handle_fee_type=HandleFeeType.TAKER,
                                                                     reason=TradeReason(TradeReasonType.ACTIVE,
                                                                                        "符合條件"))

                    # 6. 連續2次符合條件且方向相同，直接平倉 (避免過度追單)
                    return trade_if_not_trade_twice(now_trade_record, last_td)

            # 情況 B: 之前 MA7 < MA25 (空頭趨勢) 持續超過 20 期
            elif row.last_ma7_and_ma25_rel < 0 and self.is_meet_tech_idx_with_switch(row):
                # 訊號：當前 MA7 突破 MA25 (看多)
                if row.ma7 > row.ma25:
                    # ma7如果突破ma25的時候買
                    # # 如果之前做多，現在也做多，價差至少要>1000
                    # if last_td and last_td.trade_record.type == TradeType.BUY and abs(
                    #         last_td.trade_record.price - Decimal(row.ma7)) < 1000:
                    #     continue

                    # 如果之前是做空，現在要改做多，所以buy amt要包含之前做多的一起平掉 (翻多)
                    if last_td is not None:
                        handle_unit = last_td.units
                    else:
                        handle_unit = Decimal("0")

                    trade_amt = self.get_invest_amt()
                    # 若之前有空單 (handle_unit < 0)，則平倉量為 handle_unit (注意負號處理)
                    acct_handle_unit = handle_unit if handle_unit < 0 else Decimal("0")
                    trade_type = TradeType.BUY

                    # 新開倉位 - (負的持倉) = 新開 + 平倉
                    unit = trade_svc.calc_buyable_units(trade_amt, row.close) - acct_handle_unit
                    now_trade_record = trade_svc.create_trade_record(row.start_time, trade_type, row.close,
                                                                     unit=unit, handle_fee_type=HandleFeeType.TAKER,
                                                                     reason=TradeReason(TradeReasonType.ACTIVE,
                                                                                        "符合條件"))

                    # 6. 連續2次符合條件且方向相同，直接平倉
                    return trade_if_not_trade_twice(now_trade_record, last_td)
        else:
            # 未達趨勢長度門檻 (盤整中)
            logging.debug(
                f"[strategy]ma7 and ma25 diff is less than {ma7_and_ma25_rel_criteria}, abs(row.last_ma7_and_ma25_rel)[{abs(row.last_ma7_and_ma25_rel)}]")

    def get_stop_loss_trade_record(self, last_td, row):
        """
        固定點數停損機制。
        若浮動虧損超過 1000 點，則強制平倉。
        注意：這裡使用 High/Low 價格來判斷是否在 K 線期間內觸及停損點。
        """
        if last_td:
            # 計算未實現損益 (基於 Close) - 這裡僅用來檢查正負，實際虧損點數在下方邏輯計算
            unrealize_profit = trade_svc.calc_profit(Decimal(str(row.close)), last_td.handle_amt, last_td.handling_fee,
                                                     last_td.units)
            if unrealize_profit and unrealize_profit > 0:
                is_need_close = False
                # (註解掉的停利邏輯)
                # if abs(df.iloc[i - 2].ma7 - df.iloc[i - 2].ma25) > abs(df.iloc[i - 1].ma7 - df.iloc[i - 1].ma25) > abs(
                #         df.iloc[i].ma7 - df.iloc[i].ma25) < 100:
                #     is_need_close = True
                # ...
            elif unrealize_profit and unrealize_profit < 0:
                # 5. 虧損超過1000點 => 停損

                # 情況 1: 做多 (units > 0)
                # 判斷：進場均價 - 最低價 (Low) > 1000
                if last_td.units > 0 and (last_td.handle_amt / last_td.units - Decimal(str(row.low))) > 1000:
                    logging.debug("[strategy]stop loss")
                    # 以進場價 - 1000 作為停損執行價
                    return trade_svc.create_close_trade_record(row.start_time, round(
                        last_td.handle_amt / last_td.units, 2) - 1000, last_td,
                                                               reason=TradeReason(
                                                                   TradeReasonType.PASSIVE,
                                                                   "停損"))

                # 情況 2: 做空 (units < 0)
                # 判斷：最高價 (High) + 進場均價(負值) > 1000 (即 High - Entry > 1000)
                # handle_amt 為負 (或 units 為負)，需特別注意正負號邏輯
                if last_td.units < 0 and (Decimal(str(row.high)) + last_td.handle_amt / last_td.units) > 1000:
                    logging.debug("[strategy]stop loss")
                    # 以進場價(絕對值) + 1000 作為停損執行價
                    return trade_svc.create_close_trade_record(row.start_time, round(
                        last_td.handle_amt / last_td.units * -1, 2) + 1000, last_td,
                                                               reason=TradeReason(
                                                                   TradeReasonType.PASSIVE,
                                                                   "停損"))

    def fake_break(self, row):
        """
        假並破偵測 (Whipsaw Detection)。
        如果前兩次交易方向顯示市場在短時間內反覆震盪 (買->賣->買 或 賣->買->賣)，
        意圖捕捉假突破後的反回補。
        """
        if len(self.trade_detail.txn_detail_list) > 1:
            # 排除停損出場的交易，只看主動進出的交易
            non_stop_loss_td_list = [td for td in self.trade_detail.txn_detail_list if
                                     td.trade_record.reason.trade_reason_type != TradeReasonType.PASSIVE]
            last_1_td = non_stop_loss_td_list[len(non_stop_loss_td_list) - 1]
            last_2_td = non_stop_loss_td_list[len(non_stop_loss_td_list) - 2]

            # 計算上一筆交易與當前的時間差 (K線數量)
            # 注意: 這裡呼叫了外部 API 查 K 線，建議優化 (直接用 row 時間計算)
            trade_record_gap = self.binance_svc.get_historical_klines_df(self.product, self.tickets_interval,
                                                                         last_1_td.trade_record.date,
                                                                         row.start_time).shape[0] - 1

            # 條件：
            # 1. 最近兩次交易方向相反
            # 2. 上一次交易距離現在很近 (小於 5 根 K 線)
            # 3. MA 再次交叉回原方向
            # (例如：買 -> 賣 (上一筆) -> 馬上又突破 (買))
            if last_1_td.trade_record.type != last_2_td.trade_record.type \
                    and ((last_1_td.trade_record.type == TradeType.BUY and row.ma7 < row.ma25 and trade_record_gap < 5) \
                         or (
                                 last_1_td.trade_record.type == TradeType.SELL and row.ma7 > row.ma25 and trade_record_gap < 5)):
                # build trade record
                trade_type = TradeType.BUY if last_1_td.trade_record.type == TradeType.SELL else TradeType.SELL

                # if self.get_trade_index_switch_status(MaIndexSwitch.FAKE_BREAK_RSI):
                #     if (row.rsi > 80 and trade_type == TradeType.BUY) or (
                #             row.rsi < 20 and trade_type == TradeType.SELL):
                #         return None

                # 加碼? Unit 計算邏輯似乎是疊加
                unit = abs(last_2_td.units) if last_1_td.units == 0 else abs(last_2_td.units) + abs(last_1_td.units)

                touch_ma_trade_record = trade_svc.create_trade_record(row.start_time, trade_type,
                                                                      row.close,
                                                                      unit=unit,
                                                                      handle_fee_type=HandleFeeType.TAKER,
                                                                      reason=TradeReason(
                                                                          TradeReasonType.ACTIVE,
                                                                          "假突跌破，認錯回補"))
                return touch_ma_trade_record
        return None
