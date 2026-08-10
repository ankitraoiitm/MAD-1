import os
from datetime import datetime, date
from functools import wraps

from flask import (
    Flask, render_template, redirect, url_for, request, flash, abort, jsonify,
)
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user,
)
from sqlalchemy import or_

from models import (
    db, User, Trek, Booking,
    ROLE_ADMIN, ROLE_STAFF, ROLE_USER,
    STATUS_ACTIVE, STATUS_BLACKLISTED,
    TREK_PENDING, TREK_APPROVED, TREK_OPEN, TREK_CLOSED, TREK_COMPLETED,
    BOOKING_BOOKED, BOOKING_CANCELLED, BOOKING_COMPLETED,
)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "trek-dev-secret-key")
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "sqlite:///" + os.path.join(BASE_DIR, "instance", "trekking.db")
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "login"
    login_manager.login_message_category = "warning"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.context_processor
    def inject_globals():
        return dict(
            TREK_PENDING=TREK_PENDING, TREK_APPROVED=TREK_APPROVED,
            TREK_OPEN=TREK_OPEN, TREK_CLOSED=TREK_CLOSED, TREK_COMPLETED=TREK_COMPLETED,
            BOOKING_BOOKED=BOOKING_BOOKED, BOOKING_CANCELLED=BOOKING_CANCELLED,
            BOOKING_COMPLETED=BOOKING_COMPLETED,
            now=datetime.utcnow(),
        )

    register_routes(app)

    with app.app_context():
        init_db()

    return app


def init_db():
    os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)
    db.create_all()

    if not User.query.filter_by(role=ROLE_ADMIN).first():
        admin = User(
            name="Administrator",
            email="admin@trek.com",
            role=ROLE_ADMIN,
            approved=True,
            status=STATUS_ACTIVE,
            contact="0000000000",
        )
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()
        _seed_demo_data()


def _seed_demo_data():
    s1 = User(name="Ravi Guide", email="ravi@trek.com", role=ROLE_STAFF,
              approved=True, contact="9876500001")
    s1.set_password("staff123")
    s2 = User(name="Meera Sherpa", email="meera@trek.com", role=ROLE_STAFF,
              approved=False, contact="9876500002")
    s2.set_password("staff123")

    u1 = User(name="Anil Trekker", email="anil@trek.com", role=ROLE_USER,
              contact="9000000001")
    u1.set_password("user123")
    u2 = User(name="Sara Explorer", email="sara@trek.com", role=ROLE_USER,
              contact="9000000002")
    u2.set_password("user123")

    db.session.add_all([s1, s2, u1, u2])
    db.session.commit()

    t1 = Trek(name="Kedarkantha Winter Trek", location="Uttarakhand",
              difficulty="Moderate", duration=6, total_slots=20, available_slots=20,
              price=8500, status=TREK_OPEN, assigned_staff_id=s1.id,
              start_date=date(2026, 9, 10), end_date=date(2026, 9, 15),
              description="A classic snow trek with stunning summit views.")
    t2 = Trek(name="Valley of Flowers", location="Uttarakhand",
              difficulty="Easy", duration=4, total_slots=25, available_slots=25,
              price=6000, status=TREK_OPEN, assigned_staff_id=s1.id,
              start_date=date(2026, 8, 20), end_date=date(2026, 8, 23),
              description="A gentle walk through a UNESCO World Heritage meadow.")
    t3 = Trek(name="Stok Kangri Summit", location="Ladakh",
              difficulty="Hard", duration=9, total_slots=12, available_slots=12,
              price=22000, status=TREK_PENDING,
              start_date=date(2026, 10, 5), end_date=date(2026, 10, 13),
              description="A high-altitude mountaineering expedition above 6000m.")
    db.session.add_all([t1, t2, t3])
    db.session.commit()

    db.session.add(Booking(user_id=u1.id, trek_id=t1.id, status=BOOKING_BOOKED))
    t1.available_slots -= 1
    db.session.commit()


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            if current_user.is_blacklisted:
                logout_user()
                flash("Your account has been blacklisted. Contact the admin.", "danger")
                return redirect(url_for("login"))
            if current_user.is_staff and not current_user.approved:
                flash("Your staff account is awaiting admin approval.", "warning")
                return redirect(url_for("pending_approval"))
            return view(*args, **kwargs)
        return wrapper
    return decorator


def dashboard_for(user):
    if user.is_admin:
        return url_for("admin_dashboard")
    if user.is_staff:
        return url_for("staff_dashboard")
    return url_for("user_dashboard")


def register_routes(app):

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(dashboard_for(current_user))
        open_treks = Trek.query.filter_by(status=TREK_OPEN).limit(6).all()
        return render_template("index.html", treks=open_treks)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(dashboard_for(current_user))
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = User.query.filter_by(email=email).first()
            if not user or not user.check_password(password):
                flash("Invalid email or password.", "danger")
                return render_template("login.html")
            if user.is_blacklisted:
                flash("Your account has been blacklisted. Contact the admin.", "danger")
                return render_template("login.html")
            login_user(user)
            flash("Welcome back, " + user.name + "!", "success")
            if user.is_staff and not user.approved:
                return redirect(url_for("pending_approval"))
            return redirect(dashboard_for(user))
        return render_template("login.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(dashboard_for(current_user))
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            contact = request.form.get("contact", "").strip()
            password = request.form.get("password", "")
            role = request.form.get("role", ROLE_USER)

            errors = []
            if not name:
                errors.append("Name is required.")
            if not email or "@" not in email:
                errors.append("A valid email is required.")
            if len(password) < 6:
                errors.append("Password must be at least 6 characters.")
            if role not in (ROLE_USER, ROLE_STAFF):
                errors.append("Invalid role selected.")
            if User.query.filter_by(email=email).first():
                errors.append("An account with that email already exists.")

            if errors:
                for e in errors:
                    flash(e, "danger")
                return render_template("register.html", form=request.form)

            user = User(
                name=name, email=email, contact=contact, role=role,
                approved=(role == ROLE_USER),
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            if role == ROLE_STAFF:
                flash("Registration successful! An admin must approve your account "
                      "before you can access the staff dashboard.", "info")
            else:
                flash("Registration successful! You can now log in.", "success")
            return redirect(url_for("login"))
        return render_template("register.html", form={})

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("You have been logged out.", "info")
        return redirect(url_for("login"))

    @app.route("/pending")
    @login_required
    def pending_approval():
        if not (current_user.is_staff and not current_user.approved):
            return redirect(dashboard_for(current_user))
        return render_template("pending.html")

    @app.route("/admin")
    @role_required(ROLE_ADMIN)
    def admin_dashboard():
        stats = {
            "treks": Trek.query.count(),
            "open_treks": Trek.query.filter_by(status=TREK_OPEN).count(),
            "users": User.query.filter_by(role=ROLE_USER).count(),
            "staff": User.query.filter_by(role=ROLE_STAFF).count(),
            "pending_staff": User.query.filter_by(role=ROLE_STAFF, approved=False).count(),
            "bookings": Booking.query.count(),
            "active_bookings": Booking.query.filter_by(status=BOOKING_BOOKED).count(),
        }
        treks = Trek.query.all()
        popular = sorted(treks, key=lambda t: len(t.bookings), reverse=True)[:5]
        max_bookings = max((len(t.bookings) for t in popular), default=0)
        recent_bookings = Booking.query.order_by(Booking.booking_date.desc()).limit(8).all()
        return render_template(
            "admin/dashboard.html", stats=stats, popular=popular,
            max_bookings=max_bookings, recent_bookings=recent_bookings,
        )

    @app.route("/admin/treks")
    @role_required(ROLE_ADMIN)
    def admin_treks():
        q = request.args.get("q", "").strip()
        query = Trek.query
        if q:
            query = query.filter(_search_trek_filter(q))
        treks = query.order_by(Trek.created_at.desc()).all()
        all_staff = User.query.filter_by(role=ROLE_STAFF, approved=True,
                                         status=STATUS_ACTIVE).all()
        return render_template("admin/treks.html", treks=treks, q=q, all_staff=all_staff)

    @app.route("/admin/treks/new", methods=["GET", "POST"])
    @role_required(ROLE_ADMIN)
    def admin_trek_new():
        staff = User.query.filter_by(role=ROLE_STAFF, approved=True,
                                     status=STATUS_ACTIVE).all()
        if request.method == "POST":
            trek, err = _save_trek_from_form(None)
            if err:
                for e in err:
                    flash(e, "danger")
                return render_template("admin/trek_form.html", trek=None,
                                       staff=staff, form=request.form)
            db.session.add(trek)
            db.session.commit()
            flash("Trek '" + trek.name + "' created.", "success")
            return redirect(url_for("admin_treks"))
        return render_template("admin/trek_form.html", trek=None, staff=staff, form={})

    @app.route("/admin/treks/<int:trek_id>/edit", methods=["GET", "POST"])
    @role_required(ROLE_ADMIN)
    def admin_trek_edit(trek_id):
        trek = db.get_or_404(Trek, trek_id)
        staff = User.query.filter_by(role=ROLE_STAFF, approved=True,
                                     status=STATUS_ACTIVE).all()
        if request.method == "POST":
            _, err = _save_trek_from_form(trek)
            if err:
                for e in err:
                    flash(e, "danger")
                return render_template("admin/trek_form.html", trek=trek,
                                       staff=staff, form=request.form)
            db.session.commit()
            flash("Trek '" + trek.name + "' updated.", "success")
            return redirect(url_for("admin_treks"))
        return render_template("admin/trek_form.html", trek=trek, staff=staff, form={})

    @app.route("/admin/treks/<int:trek_id>/delete", methods=["POST"])
    @role_required(ROLE_ADMIN)
    def admin_trek_delete(trek_id):
        trek = db.get_or_404(Trek, trek_id)
        db.session.delete(trek)
        db.session.commit()
        flash("Trek '" + trek.name + "' removed.", "info")
        return redirect(url_for("admin_treks"))

    @app.route("/admin/treks/<int:trek_id>/assign", methods=["POST"])
    @role_required(ROLE_ADMIN)
    def admin_trek_assign(trek_id):
        trek = db.get_or_404(Trek, trek_id)
        staff_id = request.form.get("staff_id")
        if staff_id:
            staff = db.session.get(User, int(staff_id))
            if not staff or staff.role != ROLE_STAFF:
                flash("Invalid staff member.", "danger")
                return redirect(url_for("admin_treks"))
            trek.assigned_staff_id = staff.id
            if trek.status == TREK_PENDING:
                trek.status = TREK_APPROVED
            flash("Assigned " + staff.name + " to '" + trek.name + "'.", "success")
        else:
            trek.assigned_staff_id = None
            flash("Cleared staff assignment for '" + trek.name + "'.", "info")
        db.session.commit()
        return redirect(request.referrer or url_for("admin_treks"))

    @app.route("/admin/staff")
    @role_required(ROLE_ADMIN)
    def admin_staff():
        q = request.args.get("q", "").strip()
        query = User.query.filter_by(role=ROLE_STAFF)
        if q:
            query = query.filter(_search_person_filter(q))
        staff = query.order_by(User.created_at.desc()).all()
        return render_template("admin/staff.html", staff=staff, q=q)

    @app.route("/admin/staff/<int:user_id>/approve", methods=["POST"])
    @role_required(ROLE_ADMIN)
    def admin_staff_approve(user_id):
        staff = db.get_or_404(User, user_id)
        if staff.role == ROLE_STAFF:
            staff.approved = True
            staff.status = STATUS_ACTIVE
            db.session.commit()
            flash(staff.name + " approved.", "success")
        return redirect(url_for("admin_staff"))

    @app.route("/admin/user/<int:user_id>/blacklist", methods=["POST"])
    @role_required(ROLE_ADMIN)
    def admin_toggle_blacklist(user_id):
        person = db.get_or_404(User, user_id)
        if person.is_admin:
            flash("You cannot blacklist an admin.", "danger")
            return redirect(request.referrer or url_for("admin_dashboard"))
        if person.status == STATUS_BLACKLISTED:
            person.status = STATUS_ACTIVE
            flash(person.name + " reactivated.", "success")
        else:
            person.status = STATUS_BLACKLISTED
            flash(person.name + " blacklisted.", "warning")
        db.session.commit()
        return redirect(request.referrer or url_for("admin_dashboard"))

    @app.route("/admin/users")
    @role_required(ROLE_ADMIN)
    def admin_users():
        q = request.args.get("q", "").strip()
        query = User.query.filter_by(role=ROLE_USER)
        if q:
            query = query.filter(_search_person_filter(q))
        users = query.order_by(User.created_at.desc()).all()
        return render_template("admin/users.html", users=users, q=q)

    @app.route("/admin/bookings")
    @role_required(ROLE_ADMIN)
    def admin_bookings():
        bookings = Booking.query.order_by(Booking.booking_date.desc()).all()
        return render_template("admin/bookings.html", bookings=bookings)

    @app.route("/staff")
    @role_required(ROLE_STAFF)
    def staff_dashboard():
        treks = Trek.query.filter_by(assigned_staff_id=current_user.id).all()
        total_participants = sum(t.booked_count for t in treks)
        return render_template("staff/dashboard.html", treks=treks,
                               total_participants=total_participants)

    @app.route("/staff/treks/<int:trek_id>", methods=["GET", "POST"])
    @role_required(ROLE_STAFF)
    def staff_trek_manage(trek_id):
        trek = db.get_or_404(Trek, trek_id)
        if trek.assigned_staff_id != current_user.id:
            abort(403)
        if request.method == "POST":
            action = request.form.get("action")
            if action == "update":
                try:
                    new_slots = int(request.form.get("available_slots", trek.available_slots))
                except ValueError:
                    flash("Slots must be a number.", "danger")
                    return redirect(url_for("staff_trek_manage", trek_id=trek.id))
                if new_slots < trek.booked_count:
                    flash("Available slots cannot be less than current bookings "
                          "(" + str(trek.booked_count) + ").", "danger")
                    return redirect(url_for("staff_trek_manage", trek_id=trek.id))
                trek.available_slots = new_slots
                status = request.form.get("status")
                if status in (TREK_OPEN, TREK_CLOSED):
                    trek.status = status
                db.session.commit()
                flash("Trek updated.", "success")
            elif action == "start":
                trek.status = TREK_CLOSED
                db.session.commit()
                flash("Trek marked as started (bookings closed).", "info")
            elif action == "complete":
                trek.status = TREK_COMPLETED
                for b in trek.bookings:
                    if b.status == BOOKING_BOOKED:
                        b.status = BOOKING_COMPLETED
                db.session.commit()
                flash("Trek marked as completed.", "success")
            return redirect(url_for("staff_trek_manage", trek_id=trek.id))
        participants = [b for b in trek.bookings if b.status != BOOKING_CANCELLED]
        return render_template("staff/trek_manage.html", trek=trek,
                               participants=participants)

    @app.route("/dashboard")
    @role_required(ROLE_USER)
    def user_dashboard():
        bookings = Booking.query.filter_by(user_id=current_user.id).order_by(
            Booking.booking_date.desc()).all()
        active = [b for b in bookings if b.status == BOOKING_BOOKED]
        open_treks = Trek.query.filter_by(status=TREK_OPEN).limit(6).all()
        return render_template("user/dashboard.html", bookings=bookings,
                               active=active, open_treks=open_treks)

    @app.route("/treks")
    @role_required(ROLE_USER)
    def user_treks():
        q = request.args.get("q", "").strip()
        difficulty = request.args.get("difficulty", "").strip()
        location = request.args.get("location", "").strip()
        query = Trek.query.filter_by(status=TREK_OPEN)
        if q:
            query = query.filter(_search_trek_filter(q))
        if difficulty:
            query = query.filter(Trek.difficulty == difficulty)
        if location:
            query = query.filter(Trek.location.ilike("%" + location + "%"))
        treks = query.order_by(Trek.start_date.asc()).all()
        locations = [row[0] for row in db.session.query(Trek.location).distinct()]
        my_trek_ids = {
            b.trek_id for b in Booking.query.filter_by(
                user_id=current_user.id, status=BOOKING_BOOKED).all()
        }
        return render_template("user/treks.html", treks=treks, q=q,
                               difficulty=difficulty, location=location,
                               locations=locations, my_trek_ids=my_trek_ids)

    @app.route("/treks/<int:trek_id>/book", methods=["POST"])
    @role_required(ROLE_USER)
    def user_book(trek_id):
        trek = db.get_or_404(Trek, trek_id)
        if trek.status != TREK_OPEN:
            flash("This trek is not open for booking.", "danger")
            return redirect(url_for("user_treks"))
        existing = Booking.query.filter_by(
            user_id=current_user.id, trek_id=trek.id, status=BOOKING_BOOKED).first()
        if existing:
            flash("You have already booked this trek.", "warning")
            return redirect(url_for("user_bookings"))
        if trek.available_slots <= 0:
            flash("Sorry, this trek is fully booked.", "danger")
            return redirect(url_for("user_treks"))

        booking = Booking(user_id=current_user.id, trek_id=trek.id,
                          status=BOOKING_BOOKED)
        trek.available_slots -= 1
        db.session.add(booking)
        db.session.commit()
        flash("Booked '" + trek.name + "' successfully!", "success")
        return redirect(url_for("user_bookings"))

    @app.route("/bookings")
    @role_required(ROLE_USER)
    def user_bookings():
        bookings = Booking.query.filter_by(user_id=current_user.id).order_by(
            Booking.booking_date.desc()).all()
        return render_template("user/bookings.html", bookings=bookings)

    @app.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
    @role_required(ROLE_USER)
    def user_cancel(booking_id):
        booking = db.get_or_404(Booking, booking_id)
        if booking.user_id != current_user.id:
            abort(403)
        if booking.status == BOOKING_BOOKED:
            booking.status = BOOKING_CANCELLED
            if booking.trek.available_slots < booking.trek.total_slots:
                booking.trek.available_slots += 1
            db.session.commit()
            flash("Booking cancelled.", "info")
        return redirect(url_for("user_bookings"))

    @app.route("/profile", methods=["GET", "POST"])
    @role_required(ROLE_USER)
    def user_profile():
        if request.method == "POST":
            current_user.name = request.form.get("name", current_user.name).strip()
            current_user.contact = request.form.get("contact", current_user.contact).strip()
            new_pw = request.form.get("password", "")
            if new_pw:
                if len(new_pw) < 6:
                    flash("Password must be at least 6 characters.", "danger")
                    return redirect(url_for("user_profile"))
                current_user.set_password(new_pw)
            db.session.commit()
            flash("Profile updated.", "success")
            return redirect(url_for("user_profile"))
        return render_template("user/profile.html")

    @app.route("/api/treks")
    def api_treks():
        treks = Trek.query.filter_by(status=TREK_OPEN).all()
        return jsonify([
            {
                "id": t.id, "name": t.name, "location": t.location,
                "difficulty": t.difficulty, "duration": t.duration,
                "available_slots": t.available_slots, "total_slots": t.total_slots,
                "price": t.price, "status": t.status,
                "start_date": t.start_date.isoformat() if t.start_date else None,
                "end_date": t.end_date.isoformat() if t.end_date else None,
            }
            for t in treks
        ])

    @app.route("/api/stats")
    @role_required(ROLE_ADMIN)
    def api_stats():
        return jsonify({
            "treks": Trek.query.count(),
            "users": User.query.filter_by(role=ROLE_USER).count(),
            "staff": User.query.filter_by(role=ROLE_STAFF).count(),
            "bookings": Booking.query.count(),
        })

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("error.html", code=403,
                               message="You don't have access to this page."), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", code=404,
                               message="Page not found."), 404


def _search_trek_filter(q):
    conditions = [Trek.name.ilike("%" + q + "%"), Trek.location.ilike("%" + q + "%")]
    if q.isdigit():
        conditions.append(Trek.id == int(q))
    return or_(*conditions)


def _search_person_filter(q):
    conditions = [User.name.ilike("%" + q + "%"), User.email.ilike("%" + q + "%")]
    if q.isdigit():
        conditions.append(User.id == int(q))
    return or_(*conditions)


def _save_trek_from_form(trek):
    form = request.form
    errors = []

    name = form.get("name", "").strip()
    location = form.get("location", "").strip()
    difficulty = form.get("difficulty", "Easy")
    if not name:
        errors.append("Trek name is required.")
    if not location:
        errors.append("Location is required.")
    if difficulty not in ("Easy", "Moderate", "Hard"):
        errors.append("Invalid difficulty.")

    def _int(field, default=0):
        try:
            return int(form.get(field, default) or default)
        except ValueError:
            errors.append(field.replace('_', ' ').title() + " must be a number.")
            return default

    def _float(field, default=0.0):
        try:
            return float(form.get(field, default) or default)
        except ValueError:
            errors.append(field.replace('_', ' ').title() + " must be a number.")
            return default

    duration = _int("duration", 1)
    total_slots = _int("total_slots", 0)
    price = _float("price", 0.0)

    def _date(field):
        val = form.get(field, "").strip()
        if not val:
            return None
        try:
            return datetime.strptime(val, "%Y-%m-%d").date()
        except ValueError:
            errors.append("Invalid " + field.replace('_', ' ') + ".")
            return None

    start_date = _date("start_date")
    end_date = _date("end_date")
    if start_date and end_date and end_date < start_date:
        errors.append("End date cannot be before start date.")

    status = form.get("status", TREK_PENDING)
    valid_statuses = (TREK_PENDING, TREK_APPROVED, TREK_OPEN, TREK_CLOSED, TREK_COMPLETED)
    if status not in valid_statuses:
        errors.append("Invalid status.")

    if errors:
        return trek, errors

    is_new = trek is None
    if is_new:
        trek = Trek()

    booked = trek.booked_count if not is_new else 0
    if total_slots < booked:
        return trek, ["Total slots cannot be less than current bookings "
                      "(" + str(booked) + ")."]

    trek.name = name
    trek.location = location
    trek.difficulty = difficulty
    trek.duration = duration
    trek.price = price
    trek.description = form.get("description", "").strip()
    trek.start_date = start_date
    trek.end_date = end_date
    trek.status = status

    staff_id = form.get("assigned_staff_id")
    trek.assigned_staff_id = int(staff_id) if staff_id else None

    if is_new:
        trek.total_slots = total_slots
        trek.available_slots = total_slots
    else:
        delta = total_slots - trek.total_slots
        trek.total_slots = total_slots
        trek.available_slots = max(0, trek.available_slots + delta)

    return trek, []


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, port=port)
