from flask import Flask, render_template, request, redirect, url_for, flash
from flask_wtf.csrf import CSRFProtect
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import inspect, text
from functools import wraps
from datetime import datetime
import os
import re

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
database_url = os.environ.get("DATABASE_URL")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url or (
    "sqlite:///" + os.path.join(app.instance_path, "card_requests.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "0").lower() in {"1", "true", "yes"}
csrf = CSRFProtect(app)

os.makedirs(app.instance_path, exist_ok=True)
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

CARD_REQUEST_FEE = 2000
BANK_NAME = "Access Bank"
BANK_ACCOUNT_NAME = "LUKMAN UMAR"
BANK_ACCOUNT_NUMBER = "1673932526"


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    matric_no = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    requests = db.relationship("CardRequest", backref="student", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class CardRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tracking_code = db.Column(db.String(30), unique=True, nullable=False)
    card_type = db.Column(db.String(50), default="ATM Card")
    delivery_address = db.Column(db.Text, nullable=True)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(40), default="Pending")
    admin_note = db.Column(db.Text)
    fee_amount = db.Column(db.Integer, default=CARD_REQUEST_FEE, nullable=False)
    payment_status = db.Column(db.String(30), default="Unpaid", nullable=True)
    payment_reference = db.Column(db.String(100), nullable=True)
    payment_admin_note = db.Column(db.Text, nullable=True)
    payment_verified_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash("Administrator access required.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        full_name = request.form["full_name"].strip()
        # Kept to match the current User model and existing registration flow.
        # The registration page may omit matric_no. Keep the legacy database
        # column populated with an internal unique value for compatibility.
        matric_no = request.form.get("matric_no", "").strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        if not matric_no:
            matric_no = "AUTO-" + os.urandom(8).hex().upper()

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return render_template("register.html")
        if User.query.filter((User.email == email) | (User.matric_no == matric_no)).first():
            flash("Email or matriculation number already exists.", "danger")
            return render_template("register.html")

        user = User(full_name=full_name, matric_no=matric_no, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Account created successfully. You can now log in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin_dashboard" if current_user.is_admin else "dashboard"))
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("admin_dashboard" if user.is_admin else "dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    requests = CardRequest.query.filter_by(user_id=current_user.id).order_by(
        CardRequest.created_at.desc()
    ).all()
    return render_template("dashboard.html", requests=requests)


@app.route("/request-card", methods=["GET", "POST"])
@login_required
def request_card():
    if request.method == "POST":
        card_type = request.form.get("card_type", "").strip()
        delivery_address = request.form.get("delivery_address", "").strip()
        reason = request.form.get("reason", "").strip()

        allowed_card_types = {"Verve", "Visa", "MasterCard"}
        if card_type not in allowed_card_types:
            flash("Please select a valid card type.", "danger")
            return render_template("request_card.html")
        if not delivery_address:
            flash("Please enter your delivery address.", "danger")
            return render_template("request_card.html")
        if not reason:
            flash("Please provide a reason for the request.", "danger")
            return render_template("request_card.html")

        tracking_code = f"ATM-{datetime.utcnow().strftime('%Y%m%d')}-{os.urandom(3).hex().upper()}"
        card_request = CardRequest(
            tracking_code=tracking_code,
            card_type=card_type,
            delivery_address=delivery_address,
            reason=reason,
            fee_amount=CARD_REQUEST_FEE,
            payment_status="Unpaid",
            status="Pending",
            user_id=current_user.id,
        )
        db.session.add(card_request)
        db.session.commit()
        flash("Card request submitted. Transfer the ₦2,000 fee and submit your transfer reference.", "success")
        return redirect(url_for("submit_payment_reference", request_id=card_request.id))
    return render_template("request_card.html")


@app.route("/payment/<int:request_id>", methods=["GET", "POST"])
@login_required
def submit_payment_reference(request_id):
    card_request = db.session.get(CardRequest, request_id)
    if not card_request or (
        card_request.user_id != current_user.id and not current_user.is_admin
    ):
        flash("Request not found.", "danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        if current_user.is_admin:
            flash("Administrators cannot submit an applicant payment reference here.", "warning")
            return redirect(url_for("admin_dashboard"))
        if card_request.payment_status == "Verified":
            flash("Payment has already been verified.", "info")
            return redirect(url_for("track_card", request_id=card_request.id))

        reference = request.form.get("payment_reference", "").strip()
        if not reference or len(reference) > 100:
            flash("Enter a valid bank transfer reference (maximum 100 characters).", "danger")
            return render_template(
                "payment.html",
                card_request=card_request,
                fee=CARD_REQUEST_FEE,
                bank_name=BANK_NAME,
                account_name=BANK_ACCOUNT_NAME,
                account_number=BANK_ACCOUNT_NUMBER,
            )

        card_request.payment_reference = reference
        card_request.payment_status = "Pending Verification"
        card_request.payment_admin_note = None
        db.session.commit()
        flash("Transfer reference submitted. Your payment is awaiting administrator verification.", "success")
        return redirect(url_for("track_card", request_id=card_request.id))

    return render_template(
        "payment.html",
        card_request=card_request,
        fee=CARD_REQUEST_FEE,
        bank_name=BANK_NAME,
        account_name=BANK_ACCOUNT_NAME,
        account_number=BANK_ACCOUNT_NUMBER,
    )


@app.route("/track/<int:request_id>")
@login_required
def track_card(request_id):
    card_request = db.session.get(CardRequest, request_id)
    if not card_request or (
        card_request.user_id != current_user.id and not current_user.is_admin
    ):
        flash("Request not found.", "danger")
        return redirect(url_for("dashboard"))
    return render_template("track_card.html", card_request=card_request)


@app.route("/admin")
@admin_required
def admin_dashboard():
    requests = CardRequest.query.order_by(CardRequest.created_at.desc()).all()
    users = User.query.order_by(User.created_at.desc()).all()
    stats = {
        "total": len(requests),
        "pending": CardRequest.query.filter_by(status="Pending").count(),
        "processing": CardRequest.query.filter_by(status="Processing").count(),
        "ready": CardRequest.query.filter_by(status="Ready for Collection").count(),
        "collected": CardRequest.query.filter_by(status="Collected").count(),
    }
    return render_template("admin/dashboard.html", requests=requests, users=users, stats=stats)


@app.route("/admin/payments")
@admin_required
def admin_payments():
    payments = CardRequest.query.order_by(CardRequest.created_at.desc()).all()
    return render_template("admin/payments.html", requests=payments)


@app.route("/admin/payment/<int:request_id>/verify", methods=["POST"])
@admin_required
def verify_payment(request_id):
    card_request = db.session.get(CardRequest, request_id)
    if not card_request:
        flash("Request not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    decision = request.form.get("decision", "").strip()
    note = request.form.get("payment_admin_note", "").strip()

    if decision == "verify":
        if not card_request.payment_reference:
            flash("Cannot verify payment without a submitted transfer reference.", "danger")
            return redirect(url_for("admin_payments"))
        # Admin must independently confirm the transaction in the bank account.
        card_request.payment_status = "Verified"
        card_request.payment_verified_at = datetime.utcnow()
        card_request.payment_admin_note = note or "Payment verified by administrator."
    elif decision == "reject":
        card_request.payment_status = "Rejected"
        card_request.payment_verified_at = None
        card_request.payment_admin_note = note or "Payment not verified. Please contact the administrator."
    else:
        flash("Invalid payment verification decision.", "danger")
        return redirect(url_for("admin_payments"))

    db.session.commit()
    flash("Payment status updated.", "success")
    return redirect(url_for("admin_payments"))


@app.route("/admin/request/<int:request_id>/update", methods=["POST"])
@admin_required
def update_request(request_id):
    card_request = db.session.get(CardRequest, request_id)
    if not card_request:
        flash("Request not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    status = request.form.get("status", "")
    allowed = ["Pending", "Approved", "Processing", "Ready for Collection", "Collected", "Rejected"]
    if status not in allowed:
        flash("Invalid status.", "danger")
        return redirect(url_for("admin_dashboard"))

    if status in ["Approved", "Processing", "Ready for Collection", "Collected"] and card_request.payment_status != "Verified":
        flash("Payment must be verified before this card request can proceed.", "danger")
        return redirect(url_for("admin_dashboard"))

    card_request.status = status
    card_request.admin_note = request.form.get("admin_note", "").strip()
    card_request.updated_at = datetime.utcnow()
    db.session.commit()
    flash("Request updated successfully.", "success")
    return redirect(url_for("admin_dashboard"))


def migrate_card_request_columns():
    """Add payment/address columns to existing installations without deleting data."""
    inspector = inspect(db.engine)
    if "card_request" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("card_request")}
    migrations = {
        "delivery_address": "TEXT",
        "fee_amount": "INTEGER NOT NULL DEFAULT 2000",
        "payment_status": "VARCHAR(30) DEFAULT 'Unpaid'",
        "payment_reference": "VARCHAR(100)",
        "payment_admin_note": "TEXT",
        "payment_verified_at": "TIMESTAMP",
    }
    for column_name, column_definition in migrations.items():
        if column_name not in existing:
            db.session.execute(text(
                f"ALTER TABLE card_request ADD COLUMN {column_name} {column_definition}"
            ))
    db.session.commit()


def init_db():
    with app.app_context():
        db.create_all()
        migrate_card_request_columns()
        admin = User.query.filter_by(email="admin@fauz.edu.ng").first()
        configured_admin_password = os.environ.get("ADMIN_PASSWORD")
        if not admin and configured_admin_password:
            admin = User(
                full_name="System Administrator",
                matric_no="ADMIN001",
                email="admin@fauz.edu.ng",
                is_admin=True,
            )
            admin.set_password(configured_admin_password)
            db.session.add(admin)
            db.session.commit()
        elif admin and configured_admin_password:
            # A configured deployment secret can reset the known legacy default.
            admin.set_password(configured_admin_password)
            admin.is_admin = True
            db.session.commit()


# Initialize the database whenever the application process starts.
init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
