import dateutil
from pytz import timezone


def convert_shopify_datetime_to_utc(datetime):
    converted_datetime = ""
    if datetime:
        datetime = dateutil.parser.parse(datetime)
        converted_datetime = datetime.astimezone(timezone('UTC')).strftime('%Y-%m-%d %H:%M:%S')
    return converted_datetime or False
