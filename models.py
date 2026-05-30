import os
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class UserPreset(db.Model):
    """เก็บ preset configuration แยกตาม username"""
    __tablename__ = "user_presets"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False, index=True)
    name = db.Column(db.String(64), nullable=False)
    data_json = db.Column(db.Text, nullable=False, default="{}")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("username", "name", name="uq_user_preset"),
    )


class UserCredential(db.Model):
    """เก็บรหัสผ่านถาวรสำหรับให้บอทไปล็อกอิน"""
    __tablename__ = "user_credentials"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False, unique=True, index=True)
    bot_password = db.Column(db.String(256), nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserSchedule(db.Model):
    """เก็บ schedule configuration แยกตาม username"""
    __tablename__ = "user_schedules"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False, index=True)
    show_browser = db.Column(db.Boolean, default=False)
    typing_speed = db.Column(db.String(16), default="normal")
    tabs_json = db.Column(db.Text, nullable=False, default="[]")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("username", name="uq_user_schedule"),
    )


class ScheduleLastRun(db.Model):
    """ติดตาม last_run ของแต่ละ schedule tab แยกตาม username"""
    __tablename__ = "schedule_last_run"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False, index=True)
    tab_index = db.Column(db.Integer, nullable=False)
    last_run_date = db.Column(db.String(10), nullable=True)  # "YYYY-MM-DD"

    __table_args__ = (
        db.UniqueConstraint("username", "tab_index", name="uq_user_tab"),
    )
