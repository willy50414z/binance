import json
import logging
from datetime import datetime
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError
from dacite import from_dict, Config

from com.willy.binance.config.config_util import config_util
from com.willy.binance.dto.trade_detail import TradeDetail
from com.willy.binance.encoder.json_encoder import EnhanceJSONEncoder
from com.willy.binance.enums.handle_fee_type import HandleFeeType
from com.willy.binance.enums.trade_reason import TradeReasonType
from com.willy.binance.enums.trade_type import TradeType


def get_backtest_svc(test_name: str):
    aws_config = config_util("aws")
    aws_region = aws_config.get("region")
    trade_detail_bucket_name = aws_config.get(f"s3.bucket.name.{test_name}")
    if aws_region and trade_detail_bucket_name:
        return S3Service(trade_detail_bucket_name, aws_region)
    else:
        raise ValueError(
            f"can't get aws s3 info,aws_region[{aws_region}]"
            f"trade_detail_bucket_name[{trade_detail_bucket_name}]")


def s3_json_decoder(dct):
    """
    這是一個 object_hook，json.loads 在解析每個 dict 時會呼叫它。
    你可以在這裡根據 Key 值或格式決定如何還原資料。
    """
    for key, value in dct.items():
        datetime_fields = ['date']
        decimal_fields = ['units', 'price', 'amt', 'fee', 'profit', 'balance']
        if key in datetime_fields:
            dct[key] = datetime.fromisoformat(value)
        elif any(field in key for field in decimal_fields) and isinstance(value, str):
            dct[key] = Decimal(value)
    return dct


class S3Service:
    def __init__(self, bucket_name: str = "binance.bot.s3", region_name: str = None):
        """
        初始化 S3 客戶端。
        在 Lambda 環境中，這段初始化建議放在 Handler 函數外，以實現連線重用。
        """
        self.s3 = boto3.client("s3", region_name=region_name)
        self.bucket_name = bucket_name
        self.aws_config = config_util("aws")

    def write_json(self, key: str, json_str: str) -> None:
        """
        將 Python 字典轉換為 JSON 並上傳至 S3
        """
        try:
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json_str,
                ContentType="application/json"
            )
            logging.info(f"成功上傳 {key} 至 s3://{self.bucket_name}/")
        except ClientError as e:
            logging.error(f"S3 上傳失敗: {e}")
            raise

    def read_json(self, key: str):
        """
        從 S3 讀取 JSON 並解析為 Python 字典
        """
        try:
            resp = self.s3.get_object(Bucket=self.bucket_name, Key=key)
            content = resp['Body'].read().decode('utf-8')
            return json.loads(content)
        except ClientError as e:
            # 針對檔案不存在的特殊處理 (Optional)
            if e.response['Error']['Code'] == "NoSuchKey":
                logging.error(f"錯誤：找不到檔案 {key}")
                return None
            logging.error(f"S3 讀取失敗: {e}")
            raise
        except json.JSONDecodeError as e:
            logging.error(f"JSON 解析失敗: {e}")
            raise

    def write_trade_detail(self, bot_name, td: TradeDetail):
        trade_detail_key = self.aws_config.get(f"s3.bucket.file.name.{bot_name}.trade_detail")
        if trade_detail_key:
            self.write_json(trade_detail_key, json.dumps(td, cls=EnhanceJSONEncoder, ensure_ascii=False))
        else:
            raise ValueError(f"can't get trade_detail_key for save trade detail to s3")

    def get_trade_detail(self, bot_name):
        trade_detail_key = self.aws_config.get(f"s3.bucket.file.name.{bot_name}.trade_detail")
        trade_detail_json = self.read_json(trade_detail_key)
        if trade_detail_json is None:
            return TradeDetail([])
        # trade_detail_dict = json.loads(json.dumps(trade_detail_json), object_hook=s3_json_decoder)
        config = Config(type_hooks={
            datetime: datetime.fromisoformat,
            Decimal: Decimal,
            TradeType: TradeType,
            HandleFeeType: HandleFeeType,
            TradeReasonType: TradeReasonType
        })
        # 一行程式碼完成深度轉換（包含 List 和巢狀物件）
        trade_detail_obj = from_dict(
            data_class=TradeDetail,
            data=trade_detail_json,
            config=config
        )
        return trade_detail_obj


if __name__ == "__main__":
    # 1. 實例化服務
    s3_svc = S3Service(bucket_name="binance.bot.s3")
    loaded_data = s3_svc.read_json("bot_ma_7_25_break.trade_detail")
    print(loaded_data)
    # 2. 準備資料
    target_key = "data/users/123.json"
    sample_data = {
        "user_id": 123,
        "name": "Alice",
        "status": "active"
    }

    # 3. 執行操作
    try:
        # 寫入
        s3_svc.write_json(sample_data, target_key)

        # 讀取
        loaded_data = s3_svc.read_json("bot_ma_7_25_break.trade_detail")
        print("讀取到的資料:", loaded_data)
    except Exception as e:
        print(f"執行過程中發生錯誤: {e}")
