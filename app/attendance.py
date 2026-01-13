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
    today = now_kst().date()
    record = WorkLog.query.filter_by(user_id=current_user.id, work_date=today).first()
    return render_template("dashboard.html", record=record)


@attendance_bp.route("/check-in")
@login_required
def check_in():
    today = now_kst().date()
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
    today = now_kst().date()
    record = WorkLog.query.filter_by(
        user_id=current_user.id,
        work_date=today
    ).first()

    if record and not record.end_time:
        end_time = now_kst().time()
        record.end_time = end_time

        record.total_minutes, record.overtime_minutes = calculate_work_minutes(
            record.start_time, end_time, today
        )

        db.session.commit()

    return redirect(url_for("attendance.dashboard"))


def auto_checkout_if_needed(user_id):
    yesterday = now_kst().date() - timedelta(days=1)

    record = WorkLog.query.filter(
        WorkLog.user_id == user_id,
        WorkLog.work_date <= yesterday,
        WorkLog.end_time.is_(None)
    ).first()

    if record:
        check_in_dt = datetime.combine(record.date, record.start_time)

        end_dt = check_in_dt + timedelta(hours=9)

        record.end_time = end_dt.time()

        record.total_minutes, record.overtime_minutes = calculate_work_minutes(
            record.start_time, record.end_time, record.work_date
        )

        db.session.commit()
