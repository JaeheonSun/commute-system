from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required
from werkzeug.security import generate_password_hash
from .models import User, WorkLog
from . import db
from .utils import admin_required
from datetime import datetime
from sqlalchemy import extract, func
from .services import calculate_work_time, now_kst

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    users = User.query.all()
    return render_template("admin_dashboard.html", users=users)


@admin_bp.route("/create-user", methods=["POST"])
@login_required
@admin_required
def create_user():
    username = request.form["username"]
    password = request.form["password"]
    role = request.form["role"]

    if User.query.filter_by(username=username).first():
        flash("이미 존재하는 username입니다.", "warning")
        return redirect(url_for("admin.dashboard"))

    user = User(
        username=username,
        password_hash=generate_password_hash(password),
        role=role
    )
    db.session.add(user)
    db.session.commit()

    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/work-summary")
@login_required
@admin_required
def work_summary():
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)

    if not year:
        year = now_kst().year

    # 🔹 연도 목록 (드롭다운용)
    years = (
        db.session.query(extract("year", WorkLog.start_time))
        .distinct()
        .order_by(extract("year", WorkLog.start_time).desc())
        .all()
    )
    years = [int(y[0]) for y in years]

    # 🔹 기본 쿼리
    query = (
        db.session.query(
            User.username,
            func.sum(WorkLog.total_minutes).label("total_minutes"),
            func.sum(WorkLog.overtime_minutes).label("overtime_minutes"),
        )
        .join(WorkLog)
        .filter(extract("year", WorkLog.start_time) == year)
    )

    if month:
        query = query.filter(extract("month", WorkLog.start_time) == month)

    results = query.group_by(User.id).all()

    return render_template(
        "admin_work_summary.html",
        results=results,
        years=years,
        selected_year=year,
        selected_month=month,
    )

@admin_bp.route("/worklog/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_worklog():
    users = User.query.all()

    if request.method == "POST":
        user_id = request.form["user_id"]

        work_date = datetime.strptime(
            request.form["work_date"], "%Y-%m-%d"
        ).date()

        start_t = datetime.strptime(
            request.form["start_time"], "%H:%M"
        ).time()

        end_t = datetime.strptime(
            request.form["end_time"], "%H:%M"
        ).time()

        start_dt = datetime.combine(work_date, start_t)
        end_dt = datetime.combine(work_date, end_t)

        if end_dt <= start_dt:
            flash("퇴근 시간은 출근 시간보다 이후여야 합니다.", "warning")
            return redirect(request.url)
        
        existing = WorkLog.query.filter_by(
            user_id=user_id,
            work_date=work_date
        ).first()

        if existing:
            flash("이미 해당 날짜의 근무 기록이 존재합니다.", "error")
            return redirect(request.url)

        worklog = WorkLog(
            user_id=user_id,
            work_date=work_date,
            start_time=start_dt,
            end_time=end_dt,
            total_minutes=0,
            overtime_minutes=0
        )

        calculate_work_time(worklog)

        db.session.add(worklog)
        db.session.commit()

        flash("근무 기록이 추가되었습니다.", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template(
        "admin_worklog_form.html",
        users=users
    )



@admin_bp.route("/worklog/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_worklog_by_query():
    users = User.query.all()
    record = None
    selected_user = None
    selected_date = None

    if request.method == "POST":
        selected_user = int(request.form["user_id"])
        selected_date = datetime.strptime(
            request.form["work_date"], "%Y-%m-%d"
        ).date()

        # 🔍 STEP 1: 근무 기록 조회
        record = WorkLog.query.filter_by(
            user_id=selected_user,
            work_date=selected_date
        ).first()

        if not record:
            flash("해당 날짜의 근무 기록이 없습니다.", "error")
            return render_template(
                "admin_worklog_edit.html",
                users=users,
                record=None,
                selected_user=selected_user,
                selected_date=selected_date
            )

        # ✏️ STEP 2: 수정 요청인지 확인
        if "start_time" in request.form:
            start_time = datetime.strptime(
                request.form["start_time"], "%H:%M"
            ).time()
            end_time = datetime.strptime(
                request.form["end_time"], "%H:%M"
            ).time()

            start_dt = datetime.combine(selected_date, start_time)
            end_dt = datetime.combine(selected_date, end_time)

            if end_dt <= start_dt:
                flash("퇴근 시간은 출근 시간보다 이후여야 합니다.", "warning")
                return redirect(request.url)

            record.start_time = start_dt
            record.end_time = end_dt

            calculate_work_time(record)
            db.session.commit()

            flash("근무 기록이 수정되었습니다.", "success")
            return redirect(url_for("admin.dashboard"))

    return render_template(
        "admin_worklog_edit.html",
        users=users,
        record=record,
        selected_user=selected_user,
        selected_date=selected_date
    )


@admin_bp.route("/user/update", methods=["POST"])
@login_required
@admin_required
def update_user():
    user_id = request.form["user_id"]
    new_username = request.form.get("username")
    new_password = request.form.get("password")

    user = User.query.get_or_404(user_id)

    # 관리자 username 변경 방지하고 싶으면 여기서 체크 가능
    if new_username:
        existing = User.query.filter(
            User.username == new_username,
            User.id != user.id
        ).first()
        if existing:
            flash("이미 존재하는 username입니다.", "warning")
            return redirect(url_for("admin.dashboard"))

        user.username = new_username

    if new_password:
        user.password_hash = generate_password_hash(new_password)

    db.session.commit()
    flash("유저 정보가 수정되었습니다.", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/user/delete/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.role == "admin":
        flash("관리자 계정은 삭제할 수 없습니다.", "error")
        return redirect(url_for("admin.dashboard"))

    db.session.delete(user)
    db.session.commit()

    flash("유저가 삭제되었습니다.", "success")
    return redirect(url_for("admin.dashboard"))
