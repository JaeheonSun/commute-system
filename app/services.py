import holidays
from datetime import datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

def now_kst():
    return datetime.now(KST)

kr_holidays = holidays.KR()

def is_holiday(date):
    return date in kr_holidays

def is_weekend(date):
    # 월=0, 화=1 ... 토=5, 일=6
    return date.weekday() >= 5


STANDARD_WORK_MINUTES = 9 * 60

def calculate_work_minutes(start_dt, end_dt, work_date):
    start_dt = datetime.combine(work_date, start_dt)
    end_dt = datetime.combine(work_date, end_dt)

    total_minutes = int((end_dt - start_dt).total_seconds() // 60)

    if is_weekend(work_date) or is_holiday(work_date):
        return total_minutes, total_minutes

    overtime = max(0, total_minutes - STANDARD_WORK_MINUTES)
    return total_minutes, overtime



def calculate_work_time(record):
    total, overtime = calculate_work_minutes(
        record.start_time,
        record.end_time,
        record.work_date
    )

    record.total_minutes = total
    record.overtime_minutes = overtime