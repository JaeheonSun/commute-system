STANDARD_WORK_MINUTES = 9 * 60

def calculate_work_minutes(start_dt, end_dt):
    total_minutes = int((end_dt - start_dt).total_seconds() / 60)

    overtime = max(0, total_minutes - STANDARD_WORK_MINUTES)

    return total_minutes, overtime



def calculate_work_time(record):
    duration = record.end_time - record.start_time
    total_minutes = int(duration.total_seconds() // 60)

    overtime_minutes = max(0, total_minutes - 9 * 60)

    record.total_minutes = total_minutes
    record.overtime_minutes = overtime_minutes