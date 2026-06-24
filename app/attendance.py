from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from datetime import time, datetime, timedelta
from .models import WorkLog
from .services import calculate_work_minutes, now_kst, is_weekend, is_holiday

from . import db

attendance_bp = Blueprint("attendance", __name__)

@attendance_bp.route("/")
@login_required
def dashboard():
    auto_checkout_if_needed(current_user.id)
    today = now_kst().date()
    record = WorkLog.query.filter_by(user_id=current_user.id, work_date=today).first()
    return render_template("dashboard.html", record=record)


@attendance_bp.route("/check-in", methods=["GET", "POST"])
@login_required
def check_in():
    today = now_kst().date()
    record = WorkLog.query.filter_by(user_id=current_user.id, work_date=today).first()

    # If form POST, respect chosen work_type and remarks
    if request.method == "POST":
        work_type = request.form.get("work_type", "office")
        remarks = request.form.get("remarks", "")

        if record:
            flash("오늘 이미 출근 기록이 존재합니다.", "warning")
            return redirect(url_for("attendance.dashboard"))

        # For leave types, create record without times
        if work_type in ("annual_leave", "special_leave", "substitute_leave"):
            if work_type == "substitute_leave" and not remarks.strip():
                flash("대체휴무인 경우 비고(사유)를 입력해야 합니다.", "warning")
                return redirect(url_for("attendance.dashboard"))

            record = WorkLog(
                user_id=current_user.id,
                username=current_user.username,
                work_date=today,
                start_time=None,
                end_time=None,
                total_minutes=0,
                overtime_minutes=0,
                work_type=work_type,
                remarks=remarks
            )
            db.session.add(record)
            db.session.commit()
            flash("근무 형태로 기록이 저장되었습니다.", "success")
            return redirect(url_for("attendance.dashboard"))

        # Otherwise create a check-in with current time
        record = WorkLog(
            user_id=current_user.id,
            username=current_user.username,
            work_date=today,
            start_time=now_kst().time(),
            work_type=work_type,
            remarks=remarks
        )
        db.session.add(record)
        db.session.commit()
        flash("출근이 기록되었습니다.", "success")

        return redirect(url_for("attendance.dashboard"))

    # GET fallback: behave like original quick check-in
    if not record:
        record = WorkLog(
            user_id=current_user.id,
            username=current_user.username,
            work_date=today,
            start_time=now_kst().time()
        )
        db.session.add(record)
        db.session.commit()

    return redirect(url_for("attendance.dashboard"))


@attendance_bp.route("/check-out", methods=["POST", "GET"])
@login_required
def check_out():
    today = now_kst().date()
    record = WorkLog.query.filter_by(
        user_id=current_user.id,
        work_date=today
    ).first()

    if not record:
        flash("출근 기록이 없습니다.", "warning")
        return redirect(url_for("attendance.dashboard"))

    if record.end_time:
        flash("이미 퇴근 처리가 되어 있습니다.", "warning")
        return redirect(url_for("attendance.dashboard"))

    # If work_type is a leave, nothing to do
    if record.work_type in ("annual_leave", "special_leave", "substitute_leave"):
        flash("휴가/대체휴무는 퇴근 시간을 기록할 수 없습니다.", "warning")
        return redirect(url_for("attendance.dashboard"))

    end_time = now_kst().time()
    record.end_time = end_time

    # Recalculate totals
    from .services import calculate_work_time
    calculate_work_time(record)

    db.session.commit()

    flash("퇴근이 기록되었습니다.", "success")
    return redirect(url_for("attendance.dashboard"))


@attendance_bp.route("/apply-leave", methods=["POST"])
@login_required
def apply_leave():
    mode = request.form.get("mode", "single")
    remarks = request.form.get("remarks", "")

    try:
        if mode == "range":
            start_date = datetime.strptime(request.form.get("start_date", ""), "%Y-%m-%d").date()
            end_date = datetime.strptime(request.form.get("end_date", ""), "%Y-%m-%d").date()
            if end_date < start_date:
                flash("종료일은 시작일보다 이후여야 합니다.", "warning")
                return redirect(url_for("attendance.dashboard"))
            dates = []
            cur = start_date
            while cur <= end_date:
                dates.append(cur)
                cur += timedelta(days=1)
        else:
            dates = [datetime.strptime(request.form.get("leave_date", ""), "%Y-%m-%d").date()]
    except ValueError:
        flash("날짜를 올바르게 입력해주세요.", "warning")
        return redirect(url_for("attendance.dashboard"))

    invalid = [d for d in dates if is_weekend(d) or is_holiday(d)]
    if invalid:
        flash(
            f"주말 또는 공휴일이 포함되어 있어 신청할 수 없습니다: "
            f"{', '.join(d.strftime('%Y-%m-%d') for d in invalid)}",
            "warning"
        )
        return redirect(url_for("attendance.dashboard"))

    added, skipped = [], []
    for d in dates:
        if WorkLog.query.filter_by(user_id=current_user.id, work_date=d).first():
            skipped.append(d)
            continue
        db.session.add(WorkLog(
            user_id=current_user.id,
            username=current_user.username,
            work_date=d,
            start_time=time(8, 0),
            end_time=time(8, 0),
            total_minutes=0,
            overtime_minutes=0,
            work_type="annual_leave",
            remarks=remarks,
        ))
        added.append(d)
    db.session.commit()

    if added:
        flash(f"연차 {len(added)}일이 등록되었습니다.", "success")
    if skipped:
        flash(f"이미 기록이 있어 건너뛴 날짜: {', '.join(d.strftime('%m/%d') for d in skipped)}", "warning")

    return redirect(url_for("attendance.dashboard"))


@attendance_bp.route("/update-remarks", methods=["POST"])
@login_required
def update_remarks():
    today = now_kst().date()
    record = WorkLog.query.filter_by(user_id=current_user.id, work_date=today).first()

    if not record:
        flash("출근 기록이 없습니다.", "warning")
        return redirect(url_for("attendance.dashboard"))

    if record.end_time:
        flash("퇴근 후에는 비고를 수정할 수 없습니다.", "warning")
        return redirect(url_for("attendance.dashboard"))

    record.remarks = request.form.get("remarks", "")
    db.session.commit()
    flash("비고가 저장되었습니다.", "success")
    return redirect(url_for("attendance.dashboard"))


def auto_checkout_if_needed(user_id):
    yesterday = now_kst().date() - timedelta(days=1)

    record = WorkLog.query.filter(
        WorkLog.user_id == user_id,
        WorkLog.work_date <= yesterday,
        WorkLog.end_time.is_(None)
    ).first()

    if record:
        check_in_dt = datetime.combine(record.work_date, record.start_time)

        end_dt = check_in_dt + timedelta(hours=9)

        if end_dt.date() > record.work_date:
        # 자정 넘어가면 23:59로 고정
            record.end_time = time(23, 59)
        else:
            record.end_time = end_dt.time()

        record.total_minutes, record.overtime_minutes = calculate_work_minutes(
            record.start_time, record.end_time, record.work_date
        )

        db.session.commit()
