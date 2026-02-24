cd ..
RD /S /Q "target"
robocopy com target/com /MIR

xcopy "build\Dockerfile" "target" /E /I /Y

cd target
pip install -r requirements.txt
docker build -t ma_7_25_break .
docker container rm -f ma_7_25_break
docker run --name ma_7_25_break -p 9000:8080 -d ma_7_25_break

cd ..
RD /S /Q "target"

aws ecr get-login-password --region ap-southeast-1 | docker login --username AWS --password-stdin 449068335280.dkr.ecr.ap-southeast-1.amazonaws.com

docker tag ma_7_25_break 449068335280.dkr.ecr.ap-southeast-1.amazonaws.com/binance_trade_bot/ma_7_25_break:latest
docker push 449068335280.dkr.ecr.ap-southeast-1.amazonaws.com/binance_trade_bot/ma_7_25_break:latest

@REM lambdas更新到使用最新的image
aws lambda update-function-code --function-name ma_7_25_break --image-uri 449068335280.dkr.ecr.ap-southeast-1.amazonaws.com/binance_trade_bot/ma_7_25_break:latest

@REM us-east-1
@REM ap-southeast-1
@REM
@REM aws login
@REM aws ecr get-login-password --region ap-southeast-1 | docker login --username AWS --password-stdin 449068335280.dkr.ecr.ap-southeast-1.amazonaws.com
@REM
@REM docker tag aa683bd28809 449068335280.dkr.ecr.us-east-1.amazonaws.com/binance_trade_bot/ma_7_25_break:latest
@REM
@REM docker push 449068335280.dkr.ecr.us-east-1.amazonaws.com/binance_trade_bot/ma_7_25_break:latest
@REM
@REM aws events put-rule --schedule-expression "cron(0,15,30,45 * * * ? *)" --name ma_7_25_break_rule --region ap-southeast-1