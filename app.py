from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
database_url = os.environ.get("DATABASE_URL")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url or ("sqlite:///" + os.path.join(app.instance_path, "card_requests.db"))
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

os.makedirs(app.instance_path, exist_ok=True)
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

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
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(40), default="Pending")
    admin_note = db.Column(db.Text)
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
        matric_no = request.form["matric_no"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

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

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    requests = CardRequest.query.filter_by(user_id=current_user.id).order_by(CardRequest.created_at.desc()).all()
    return render_template("dashboard.html", requests=requests)

@app.route("/request-card", methods=["GET", "POST"])
@login_required
def request_card():
    if request.method == "POST":
        reason = request.form["reason"].strip()
        if not reason:
            flash("Please provide a reason for the request.", "danger")
            return render_template("request_card.html")

        tracking_code = f"ATM-{datetime.utcnow().strftime('%Y%m%d')}-{os.urandom(3).hex().upper()}"
        card_request = CardRequest(
            tracking_code=tracking_code,
            card_type="ATM Card",
            reason=reason,
            user_id=current_user.id
        )
        db.session.add(card_request)
        db.session.commit()
        flash(f"Request submitted. Tracking code: {tracking_code}", "success")
        return redirect(url_for("track_card", request_id=card_request.id))
    return render_template("request_card.html")

@app.route("/track/<int:request_id>")
@login_required
def track_card(request_id):
    card_request = db.session.get(CardRequest, request_id)
    if not card_request or (card_request.user_id != current_user.id and not current_user.is_admin):
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

@app.route("/admin/request/<int:request_id>/update", methods=["POST"])
@admin_required
def update_request(request_id):
    card_request = db.session.get(CardRequest, request_id)
    if not card_request:
        flash("Request not found.", "danger")
        return redirect(url_for("admin_dashboard"))
    status = request.form["status"]
    allowed = ["Pending", "Approved", "Processing", "Ready for Collection", "Collected", "Rejected"]
    if status not in allowed:
        flash("Invalid status.", "danger")
        return redirect(url_for("admin_dashboard"))
    card_request.status = status
    card_request.admin_note = request.form.get("admin_note", "").strip()
    card_request.updated_at = datetime.utcnow()
    db.session.commit()
    flash("Request updated successfully.", "success")
    return redirect(url_for("admin_dashboard"))

def init_db():
    with app.app_context():
        db.create_all()
        admin = User.query.filter_by(email="admin@fauz.edu.ng").first()
        if not admin:
            admin = User(
                full_name="System Administrator",
                matric_no="ADMIN001",
                email="admin@fauz.edu.ng",
                is_admin=True
            )
            admin.set_password(os.environ.get("ADMIN_PASSWORD", "admin123"))
            db.session.add(admin)
            db.session.commit()

# Initialize the database whenever the application process starts.
# This runs for both local Flask and production Gunicorn workers.
init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
