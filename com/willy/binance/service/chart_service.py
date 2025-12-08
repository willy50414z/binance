from decimal import Decimal

import pandas as pd
from pandas import DataFrame
from pyecharts import options as opts
from pyecharts.charts import Line

from com.willy.binance.enums.trade_type import TradeType
from com.willy.binance.service import trade_svc


def export_trade_point_chart(chart_name, df, ma_dca_backtest_req):
    # df = pd.read_csv('E:/code/binance/data/BTCUSDT_15m.csv')

    # 提取数据中的日期和收盘价
    date_list = df['start_time'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist()
    # date_list = [(dt + relativedelta(**{"hours": 8})).strftime('%Y-%m-%d %H:%M:%S') for dt in date_list]
    close_list = df['close'].values.tolist()
    ma7_list = df["ma7"].values.tolist()
    ma25_list = df["ma25"].values.tolist()

    buy_point_list = []
    sell_point_list = []
    stop_loss_point_list = []
    total_profit_list = []
    for row in df.itertuples(index=False):
        if not pd.isna(row.txn_detail):
            if row.txn_detail.trade_record.reason.desc == "停損":
                stop_loss_point_list.append((row.start_time.strftime('%Y-%m-%d %H:%M:%S'), row.close, "STOP_LOSS"))
            else:
                if row.txn_detail.trade_record.type == TradeType.BUY:
                    buy_point_list.append((row.start_time.strftime('%Y-%m-%d %H:%M:%S'), row.close, "BUY"))
                else:
                    sell_point_list.append((row.start_time.strftime('%Y-%m-%d %H:%M:%S'), row.close, "SEll"))
            total_profit_list.append(row.txn_detail.total_profit)
        else:
            if len(total_profit_list) > 0:
                total_profit_list.append(total_profit_list[len(total_profit_list) - 1])
            else:
                total_profit_list.append(Decimal(0))

    line_chart = Line()
    line_chart.add_xaxis(xaxis_data=date_list)
    line_chart.add_yaxis(series_name="close", is_symbol_show=False,
                         y_axis=close_list, color='#000000', yaxis_index=0)
    line_chart.add_yaxis(series_name="ma7", is_symbol_show=False,
                         y_axis=ma7_list, color='#F19C38', yaxis_index=0)
    line_chart.add_yaxis(series_name="ma25", is_symbol_show=False,
                         y_axis=ma25_list, color='#EA3DF7', yaxis_index=0)
    line_chart.add_yaxis(series_name="total_profit", is_symbol_show=False,
                         y_axis=total_profit_list, color='#138535', yaxis_index=1)
    line_chart.extend_axis(yaxis=opts.AxisOpts(type_="value", position="right"))
    line_chart.set_series_opts(
        markpoint_opts=opts.MarkPointOpts(
            data=[opts.MarkPointItem(name=f"{p[0]} {p[1]}", itemstyle_opts={"color": "#2EBD85"}, coord=[p[0], p[1]]) for
                  p in
                  buy_point_list]
                 + [opts.MarkPointItem(name=f"{p[0]} {p[1]}", itemstyle_opts={"color": "#F6465D"}, coord=[p[0], p[1]])
                    for p in
                    sell_point_list] + [
                     opts.MarkPointItem(name=f"{p[0]} {p[1]}", itemstyle_opts={"color": "#00A2E8"}, coord=[p[0], p[1]])
                     for p in
                     stop_loss_point_list]

        ))

    line_chart.set_global_opts(
        title_opts=opts.TitleOpts(title="ma_dca data"),
        xaxis_opts=opts.AxisOpts(type_="category"),
        yaxis_opts=opts.AxisOpts(type_="value", name="price", is_scale=True),
        datazoom_opts=[
            opts.DataZoomOpts(
                pos_bottom="-2%",
                range_start=0,
                range_end=100,
                type_="inside"
            ),
            opts.DataZoomOpts(
                pos_bottom="-2%",
                range_start=0,
                range_end=100,
                type_="slider",
            ),
        ],
        tooltip_opts=opts.TooltipOpts(trigger="axis"),
        toolbox_opts=opts.ToolboxOpts(
            feature={
                "dataZoom": {"yAxisIndex": "none"},
                "restore": {},
                "saveAsImage": {},
            }
        ),
    )

    # line_chart.render(f"E:/code/binance/charts/{chart_name}.html")

    chart_html = line_chart.render_embed()

    # Convert DataFrame to HTML table
    txn_detail_df = df[df['txn_detail'].notna()][["start_time", "txn_detail"]]
    df2 = DataFrame()
    df2['date'] = txn_detail_df['txn_detail'].apply(lambda d: d.trade_record.date.strftime('%Y%m%d %H:%M:%S'))
    df2['units'] = txn_detail_df['txn_detail'].apply(lambda d: d.units)
    df2['price'] = txn_detail_df['txn_detail'].apply(lambda d: round(d.trade_record.price, 2))
    df2['profit'] = txn_detail_df['txn_detail'].apply(lambda d: d.profit)
    df2['total_profit'] = txn_detail_df['txn_detail'].apply(lambda d: d.total_profit)
    df2['reason'] = txn_detail_df['txn_detail'].apply(lambda d: d.trade_record.reason.desc)
    table_html = df2.to_html(index=False, border=1)

    strategy_summary_df = trade_svc.analyze_trading_strategy(df2, ma_dca_backtest_req["initial_capital"])
    strategy_summary_html = strategy_summary_df.to_html(index=False, border=1)
    # strategy_summary_html = ""

    # Combine
    final_html = """
    <!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>交易策略回測結果</title>
    <style>
    /* 設置根容器使用 Grid 佈局 */
    .grid-container {
        display: grid;
        /* *** 關鍵變動：增加一行 auto *** */
        /* 第 1 行 (Request Info): auto (由內容決定) */
        /* 第 2 行 (Summary): auto (由內容決定) */
        /* 第 3 行 (Chart/Table): 1fr (佔據所有剩餘空間) */
        grid-template-rows: auto auto 1fr; 
        
        /* 定義兩列: 讓 chart 和 table 各佔據一半寬度 */
        grid-template-columns: 1fr 1fr; 
        
        gap: 10px; /* 元素之間的間距 */
        padding: 10px;
        /* 設置容器高度為整個視口，讓 1fr 有確定的高度可以依據 */
        height: 100vh; 
        box-sizing: border-box; /* 確保 padding 不會增加總高度 */
    }

    /* 新增：用於放置 Request 資訊的容器 (第 1 行) */
    .request-info {
        grid-row: 1 / 2;         /* 放在第 1 行 */
        grid-column: 1 / 3;     /* 跨越兩欄 */
        padding: 10px;
        border: 1px solid #ddd;
        background-color: #f0fff0; /* 淺綠色背景以區分 */
    }

    /* 策略總結放在第 2 行 (原來的第 1 行) */
    .strategy-summary {
        grid-row: 2 / 3;        /* 調整到第 2 行 */
        grid-column: 1 / 3; 
        padding: 15px;
        border: 1px solid #ddd;
        background-color: #f9f9f9;
    }

    /* 圖表和表格容器 (第 3 行，原來的第 2 行) */
    .chart, .table {
        grid-row: 3 / 4;        /* 調整到第 3 行 */
        display: flex; /* 啟用 Flexbox */
        flex-direction: column; 
        min-height: 0; 
    }

    .chart {
        grid-column: 1 / 2; 
        overflow: auto; 
    }

    /* 交易紀錄表放在第 3 行第 2 欄 */
    .table {
        grid-column: 2 / 3; 
        overflow: hidden; 
    }

    /* 針對內容區域創建一個專用的 DIV，確保它佔滿剩餘高度並可以滾動 */
    .table-content {
        flex-grow: 1; /* 佔滿所有剩餘的垂直空間 */
        overflow-y: auto; /* 內容溢出時在此區域滾動 */
    }
    
    /* 確保 body 和 html 不會有額外的邊距 */
    body, html {
        margin: 0;
        padding: 0;
        font-family: Arial, sans-serif;
        height: 100%; 
    }

    /* 針對 request 資訊的表格增加樣式 */
    .request-table {
        width: 100%;
        border-collapse: collapse;
    }
    .request-table th, .request-table td {
        border: 1px solid #ccc;
        padding: 8px;
        text-align: left;
    }
    .request-table th {
        background-color: #e0e0e0;
    }
</style>
</head>
<body>
    <div class="grid-container">

        <div class="request-info">
            <h2>📝 請求資訊</h2>
            <table class="request-table">
                <thead>
                    <tr>
                        <th>欄位名稱</th>
                        <th>值</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>request</td>
                        <td>""" + str(ma_dca_backtest_req) + """"</td>
                    </tr>
                </tbody>
            </table>
        </div>
        <div class="strategy-summary">
            <h2>📈 策略分析總結</h2>
            """ + strategy_summary_html + """
        </div>

        <div class="chart">
            <h2>📊 淨值曲線圖</h2>
            """ + chart_html + """
        </div>

        <div class="table">
            <h2>📋 交易紀錄詳情</h2>
            <div class="table-content">
                """ + table_html + """
            </div>
        </div>

    </div>
</body>
</html>
    """

    with open(f"E:/code/binance/charts/{chart_name}.html", "w", encoding="utf-8") as f:
        f.write(final_html)

    # line_chart2 = Line()
    # line_chart2.add_xaxis(xaxis_data=date_list)
    # line_chart2.add_yaxis(series_name="total_profit", is_symbol_show=False,
    #                       y_axis=total_profit_list, color='#000000')
    #
    # line_chart2.set_global_opts(
    #     title_opts=opts.TitleOpts(title="total_profit data"),
    #     xaxis_opts=opts.AxisOpts(type_="category"),
    #     yaxis_opts=opts.AxisOpts(is_scale=True),
    #     datazoom_opts=[
    #         opts.DataZoomOpts(
    #             pos_bottom="-2%",
    #             range_start=0,
    #             range_end=100,
    #             type_="inside"
    #         ),
    #         opts.DataZoomOpts(
    #             pos_bottom="-2%",
    #             range_start=0,
    #             range_end=100,
    #             type_="slider",
    #         ),
    #     ],
    #     toolbox_opts=opts.ToolboxOpts(
    #         feature={
    #             "dataZoom": {"yAxisIndex": "none"},
    #             "restore": {},
    #             "saveAsImage": {},
    #         }
    #     ),
    # )

    # grid = Grid()
    # grid.add(line_chart, grid_opts=opts.GridOpts(pos_left="5%", pos_right="55%", height="400px"))
    # grid.add(line_chart2, grid_opts=opts.GridOpts(pos_left="60%", pos_right="5%", height="400px"))
    #
    # # grid.set_global_opts(
    # #     title_opts=opts.TitleOpts(title="Two charts with shared X-axis"),
    # # )
    #
    # grid.render("two_charts_nested_grid.html")


#     line = (
#         Line()
#         .add_xaxis(date_list)
#         .add_yaxis("close", y_axis=close_list, symbol="emptyCircle", is_symbol_show=True)
#         # .add_yaxis("ma7", ma7_list, symbol="emptyCircle", is_symbol_show=True, color="#3470C6")
#         # .add_yaxis("ma25", ma25_list, symbol="emptyCircle", is_symbol_show=True, color="#5470C6")
#         # .set_series_opts(
#         #     markpoint_opts=opts.MarkPointOpts(
#         #         data=[opts.MarkPointItem(name="BUY", coord=[p[0], p[1]]) for p in buy_point_list] +
#         #              [opts.MarkPointItem(name="SELL", coord=[p[0], p[1]]) for p in sell_point_list]  # 依需求調整
#         #     )
#         #     # TODO color
#         # )
#         .set_global_opts(
#             title_opts=opts.TitleOpts(title="多折線 + 自訂標註點" if chart_name is None else chart_name),
#             xaxis_opts=opts.AxisOpts(type_="date"),
#             yaxis_opts=opts.AxisOpts(name="price")
#         )
#     )
#
#     line.render(f"E:/code/binance/charts/{chart_name}.html")
#
#
if __name__ == '__main__':
    export_trade_point_chart("xxx", None)
