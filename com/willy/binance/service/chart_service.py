import pandas as pd
from pyecharts import options as opts
from pyecharts.charts import Line

from com.willy.binance.service import trade_svc


def get_mark_points(analysis_df):
    """從 analysis_df 提取交易標註點"""
    mark_points = []
    txn_rows = analysis_df[analysis_df['trade_type'].notna()]
    for timestamp, row in txn_rows.iterrows():
        label = f"{row['trade_type']}\n{row['trade_reason']}"
        color = "#000000"
        if "停損" in str(row['trade_reason']):
            color = "#00A2E8"
        elif row['trade_type'] == 'BUY':
            color = "#2EBD85"
        elif row['trade_type'] == 'SELL':
            color = "#F6465D"
        mark_points.append(opts.MarkPointItem(
            name=label,
            coord=[timestamp.strftime('%Y-%m-%d %H:%M:%S'), float(row['close'])],
            itemstyle_opts=opts.ItemStyleOpts(color=color)
        ))
    return mark_points


def export_trade_point_chart(chart_name, analysis_df, ma_dca_backtest_req):
    """
        使用 analysis_df 繪製交易點位圖
        analysis_df 預期包含: start_time (index), close, ma7, ma25, trade_type, trade_reason, profit
        """
    # 1. 準備基礎座標軸資料
    # 將 index (start_time) 轉為字串格式供圖表顯示
    date_list = analysis_df.index.strftime('%Y-%m-%d %H:%M:%S').tolist()
    close_list = analysis_df['close'].tolist()
    ma7_list = analysis_df['ma7'].tolist()
    ma25_list = analysis_df['ma25'].tolist()

    # 遍歷 DataFrame 找出有交易紀錄的行
    # 我們利用 'trade_type' 欄位是否為 NaN 來判斷
    txn_rows = analysis_df[analysis_df['trade_type'].notna()]
    profit_series = (
        pd.to_numeric(analysis_df['total_profit'], errors='coerce')  # 強制轉為數值，非數值變 NaN
        .ffill()  # 向前填充
        .fillna(0)  # 剩下的填 0
        .tolist()
    )

    for timestamp, row in txn_rows.iterrows():
        time_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
        price = float(row['close'])
        label = f"{row['trade_type']}\n{row['trade_reason']}"

        # 根據交易類型或理由分類標籤
        point_item = opts.MarkPointItem(name=label, coord=[time_str, price], value=row['trade_type'])

    line_chart = Line()
    line_chart.add_xaxis(xaxis_data=date_list)
    line_chart.add_yaxis(series_name="close", is_symbol_show=False,
                         y_axis=close_list, color='#000000', yaxis_index=0)
    line_chart.add_yaxis(series_name="ma7", is_symbol_show=False,
                         y_axis=ma7_list, color='#F19C38', yaxis_index=0)
    line_chart.add_yaxis(series_name="ma25", is_symbol_show=False,
                         y_axis=ma25_list, color='#EA3DF7', yaxis_index=0)
    line_chart.add_yaxis(series_name="accu_profit", is_symbol_show=False,
                         y_axis=profit_series, color='#138535', yaxis_index=1)
    line_chart.extend_axis(yaxis=opts.AxisOpts(type_="value", position="right"))
    line_chart.set_series_opts(
        markpoint_opts=opts.MarkPointOpts(
            data=get_mark_points(analysis_df),  # 提取買賣點的輔助函式
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
    # 1. 篩選出有交易的行
    txn_rows = analysis_df[analysis_df['trade_type'].notna()].copy()

    # 2. 格式化輸出表格用的 DataFrame
    # 我們只需要取出我們要展示的欄位，並做簡單格式化
    if len(txn_rows) > 0:
        output_df = pd.DataFrame({
            'date': txn_rows.index.strftime('%Y-%m-%d %H:%M:%S'),
            'type': txn_rows['trade_type'].values,  # 使用 .values 轉為純陣列，避開索引對齊
            'units': txn_rows['units'].values,
            'price': txn_rows['trade_price'].round(2).values,
            'profit': txn_rows['profit'].round(2).values,
            'total_profit': txn_rows['total_profit'].round(2).values,
            'acct_balance': txn_rows['acct_balance'].round(2).values,
            'reason': txn_rows['trade_reason'].values
        })
    else:
        output_df = pd.DataFrame(columns=[
            'date',
            'type',
            'units',
            'price',
            'profit',
            'total_profit',
            'acct_balance',
            'reason'
        ])
    table_html = output_df.to_html(index=False, border=1)

    strategy_summary_df = trade_svc.analyze_trading_strategy(output_df, ma_dca_backtest_req["initial_capital"])
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


if __name__ == '__main__':
    export_trade_point_chart("xxx", None)
