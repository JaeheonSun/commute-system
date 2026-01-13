from . import db, login_manager
from flask_login import UserMixin

class User(UserMixin, db.Model):
    __table_args__ = {"sqlite_autoincrement": True}
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(10), default="employee")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class WorkLog(db.Model):
    __table_args__ = (
        db.UniqueConstraint('user_id', 'work_date', name='uq_worklog_user_date'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    username = db.Column(db.String(50))
    work_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time)
    total_minutes = db.Column(db.Integer)
    overtime_minutes = db.Column(db.Integer)