from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

ROLE_ADMIN = "admin"
ROLE_STAFF = "staff"
ROLE_USER = "user"

STATUS_ACTIVE = "active"
STATUS_BLACKLISTED = "blacklisted"

TREK_PENDING = "Pending"
TREK_APPROVED = "Approved"
TREK_OPEN = "Open"
TREK_CLOSED = "Closed"
TREK_COMPLETED = "Completed"

BOOKING_BOOKED = "Booked"
BOOKING_CANCELLED = "Cancelled"
BOOKING_COMPLETED = "Completed"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    contact = db.Column(db.String(40))
    role = db.Column(db.String(20), nullable=False, default=ROLE_USER)
    approved = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), nullable=False, default=STATUS_ACTIVE)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assigned_treks = db.relationship(
        "Trek", back_populates="staff", foreign_keys="Trek.assigned_staff_id"
    )
    bookings = db.relationship(
        "Booking", back_populates="user", cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == ROLE_ADMIN

    @property
    def is_staff(self):
        return self.role == ROLE_STAFF

    @property
    def is_trekker(self):
        return self.role == ROLE_USER

    @property
    def is_blacklisted(self):
        return self.status == STATUS_BLACKLISTED


class Trek(db.Model):
    __tablename__ = "treks"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    location = db.Column(db.String(160), nullable=False)
    difficulty = db.Column(db.String(20), nullable=False, default="Easy")
    duration = db.Column(db.Integer, nullable=False, default=1)
    total_slots = db.Column(db.Integer, nullable=False, default=0)
    available_slots = db.Column(db.Integer, nullable=False, default=0)
    price = db.Column(db.Float, default=0.0)
    description = db.Column(db.Text, default="")
    status = db.Column(db.String(20), nullable=False, default=TREK_PENDING)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    assigned_staff_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    staff = db.relationship(
        "User", back_populates="assigned_treks", foreign_keys=[assigned_staff_id]
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    bookings = db.relationship(
        "Booking", back_populates="trek", cascade="all, delete-orphan"
    )

    @property
    def booked_count(self):
        return sum(1 for b in self.bookings if b.status == BOOKING_BOOKED)

    @property
    def is_bookable(self):
        return self.status == TREK_OPEN and self.available_slots > 0

    @property
    def difficulty_badge(self):
        return {
            "Easy": "success",
            "Moderate": "warning",
            "Hard": "danger",
        }.get(self.difficulty, "secondary")

    @property
    def status_badge(self):
        return {
            TREK_PENDING: "secondary",
            TREK_APPROVED: "info",
            TREK_OPEN: "success",
            TREK_CLOSED: "dark",
            TREK_COMPLETED: "primary",
        }.get(self.status, "secondary")


class Booking(db.Model):
    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    trek_id = db.Column(db.Integer, db.ForeignKey("treks.id"), nullable=False)
    booking_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default=BOOKING_BOOKED)

    user = db.relationship("User", back_populates="bookings")
    trek = db.relationship("Trek", back_populates="bookings")

    @property
    def status_badge(self):
        return {
            BOOKING_BOOKED: "success",
            BOOKING_CANCELLED: "danger",
            BOOKING_COMPLETED: "primary",
        }.get(self.status, "secondary")
