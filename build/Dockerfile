# 使用 AWS Lambda 官方 Python 基礎映像
# 建議使用最新的穩定版本，例如 Python 3.12
FROM public.ecr.aws/lambda/python:3.14

# 設定容器內的工作目錄
WORKDIR /var/task



# 複製您的整個 python 資料夾到容器的 /var/task
# /var/task 是 Lambda 執行時存儲程式碼的標準路徑
# 您的程式碼和 requirements.txt 現在位於 /var/task/python/
COPY com /var/task/com
COPY requirements.txt /var/task/requirements.txt
RUN pip install --target /var/task -r requirements.txt

CMD [ "com.willy.binance.aws.bot.ma_7_25_break.lambda_handler" ]
