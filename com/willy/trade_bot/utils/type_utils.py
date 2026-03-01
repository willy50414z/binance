import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def str_date_to_timestamp(yyyymmdd):
    dt = datetime.strptime(yyyymmdd, "%Y%m%d")
    # If you want milliseconds since epoch in UTC
    dt_utc = dt.replace(tzinfo=timezone.utc)
    return int(dt_utc.timestamp() * 1000)


def timestamp_to_datetime(timestamp: int, tz=None):
    try:
        return datetime.fromtimestamp(timestamp, tz=tz)
    except Exception as e:
        logging.error(f"[timestamp_to_datetime]fail,timestamp[{timestamp}]", e)
        raise e


def datetime_to_str(dt: datetime, format="%Y%m%d"):
    return dt.strftime(format)


def datetime_to_str_ms(dt: datetime, format="%Y%m%d"):
    ms = int(dt.microsecond / 1000)
    return dt.strftime(format) + f".{ms:03d}"


def str_to_date(str):
    return datetime.strptime(str, "%Y%m%d").replace(tzinfo=ZoneInfo("UTC"))


def str_to_date_min(str):
    return datetime.strptime(str, "%Y%m%d%H%M").replace(tzinfo=ZoneInfo("UTC"))


def str_to_datetime(s: str = "2025-10-01T00:00:00Z"):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))
