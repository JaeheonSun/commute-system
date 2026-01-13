from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from datetime import date, datetime, timedelta
from .models import WorkLog
from .services import calculate_work_minutes, now_kst

from . import db

attendance_bp = Blueprint("attendance", __name__)

@attendance_bp.route("/")
@login_required
def dashboard():
    auto_checkout_if_needed(current_user.id)
    today = date.today()
    record = WorkLog.query.filter_by(user_id=current_user.id, work_date=today).first()
    return render_template("dashboard.html", record=record)


@attendance_bp.route("/check-in")
@login_required
def check_in():
    today = date.today()
    record = WorkLog.query.filter_by(user_id=current_user.id, work_date=today).first()
    if not record:
        record = WorkLog(
            user_id=current_user.id,
            work_date=today,
            start_time=now_kst().time()
        )
        db.session.add(record)
        db.session.commit()
    return redirect(url_for("attendance.dashboard"))


@attendance_bp.route("/check-out")
@login_required
def check_out():
    today = date.today()
    record = WorkLog.query.filter_by(
        user_id=current_user.id,
        work_date=today
    ).first()

    if record and not record.check_out:
        end_time = now_kst()
        record.check_out = end_time.time()

        start_dt = datetime.combine(today, record.check_in)
        total_minutes, overtime_minutes = calculate_work_minutes(
            start_dt, end_time, today
        )

        worklog = WorkLog(
            user_id=current_user.id,
            work_date=today,
            start_time=start_dt,
            end_time=end_time,
            total_minutes=total_minutes,
            overtime_minutes=overtime_minutes
        )

        db.session.add(worklog)
        db.session.commit()

    return redirect(url_for("attendance.dashboard"))


def auto_checkout_if_needed(user_id):
    yesterday = date.today() - timedelta(days=1)

    record = WorkLog.query.filter(
        WorkLog.user_id == user_id,
        WorkLog.work_date <= yesterday,
        WorkLog.end_time.is_(None)
    ).first()

    if record:
        check_in_dt = datetime.combine(record.date, record.check_in)

        end_dt = check_in_dt + timedelta(hours=9)

        record.end_time = end_dt.time()

        start_dt = datetime.combine(record.date, record.check_in)

        record.total_minutes, record.overtime_minutes = calculate_work_minutes(
            start_dt, end_dt
        )

        db.session.commit()
