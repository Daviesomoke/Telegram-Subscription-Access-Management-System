









import os
import asyncio
from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime, timedelta
from models import SessionLocal, User, Group
from config import ADMIN_PASSWORD


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def create_app(bot_app=None):
    app = Flask(__name__)
    app.secret_key = os.getenv("SECRET_KEY", "fallback-secret-key-change-me")
    app.config['BOT_APP'] = bot_app

    def login_required(view):
        from functools import wraps
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("admin"):
                return redirect(url_for("login"))
            return view(*args, **kwargs)
        return wrapped

    @app.route("/")
    def index():
        return redirect(url_for("login"))

    @app.route("/health")
    def health():
        return "OK", 200

    @app.route("/admin/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            if request.form.get("password") == ADMIN_PASSWORD:
                session["admin"] = True
                return redirect(url_for("dashboard"))
            flash("Wrong password", "error")
        return render_template("admin_login.html")

    @app.route("/admin/logout")
    def logout():
        session.pop("admin", None)
        return redirect(url_for("login"))

    @app.route("/admin/dashboard")
    @login_required
    def dashboard():
        db = SessionLocal()
        try:
            pending = db.query(User).filter_by(payment_status="pending").all()
            approved = db.query(User).filter(
                User.payment_status == "approved",
                User.expiry_date > datetime.utcnow(),
                User.banned == False,
            ).order_by(User.expiry_date).all()
            expired = db.query(User).filter(
                User.payment_status == "approved",
                User.expiry_date <= datetime.utcnow(),
            ).all()
            return render_template("dashboard.html",
                                   pending=pending,
                                   approved=approved,
                                   expired=expired)
        except Exception as e:
            flash(f"Database error: {e}", "error")
            return render_template("dashboard.html", pending=[], approved=[], expired=[])
        finally:
            db.close()

    @app.route("/admin/approve/<int:telegram_id>", methods=["POST"])
    @login_required
    def approve_user(telegram_id):
        db = SessionLocal()
        try:
            user = db.query(User).get(telegram_id)
            if not user:
                flash("User not found", "error")
                return redirect(url_for("dashboard"))
            if not user.group_id:
                flash("User has no group assigned.", "error")
                return redirect(url_for("dashboard"))
            group = db.query(Group).get(user.group_id)
            if not group:
                flash("Group not found.", "error")
                return redirect(url_for("dashboard"))
            bot = app.config.get('BOT_APP').bot if app.config.get('BOT_APP') else None
            if not bot:
                flash("Bot not available.", "error")
                return redirect(url_for("dashboard"))
            now = datetime.utcnow()
            days = int(request.form.get("days", 30))
            if user.payment_status == "approved" and user.expiry_date and user.expiry_date > now:
                user.expiry_date += timedelta(days=days)
            else:
                user.expiry_date = now + timedelta(days=days)
            user.payment_status = "approved"
            user.banned = False
            try:
                invite = run_async(bot.create_chat_invite_link(
                    chat_id=group.chat_id,
                    member_limit=1,
                    name=f"User_{telegram_id}"
                ))
                user.invite_link = invite.invite_link
                user.invite_link_used = False
            except Exception as e:
                flash(f"Failed to create invite link: {e}", "error")
                db.rollback()
                return redirect(url_for("dashboard"))
            db.commit()
            try:
                run_async(bot.send_message(
                    chat_id=telegram_id,
                    text=(
                        "✅ Subscription approved.\n"
                        f"Group: {group.name}\n"
                        f"Your access expires on: {user.expiry_date.strftime('%Y-%m-%d %H:%M')} UTC\n\n"
                        f"One-time invite link: {user.invite_link}\n"
                        "This link works only for your account - do not share it."
                    )
                ))
            except Exception:
                pass
            flash(f"User {telegram_id} approved, invite link sent.", "success")
        finally:
            db.close()
        return redirect(url_for("dashboard"))

    @app.route("/admin/reject/<int:telegram_id>", methods=["POST"])
    @login_required
    def reject_user(telegram_id):
        db = SessionLocal()
        try:
            user = db.query(User).get(telegram_id)
            if user:
                user.payment_status = "rejected"
                db.commit()
                bot = app.config.get('BOT_APP').bot if app.config.get('BOT_APP') else None
                if bot:
                    try:
                        run_async(bot.send_message(
                            chat_id=telegram_id,
                            text="❌ Your payment was rejected. Please contact support."
                        ))
                    except Exception:
                        pass
                flash(f"User {telegram_id} rejected.", "warning")
        finally:
            db.close()
        return redirect(url_for("dashboard"))

    @app.route("/admin/extend/<int:telegram_id>", methods=["POST"])
    @login_required
    def extend_user(telegram_id):
        days = int(request.form.get("days", 30))
        db = SessionLocal()
        try:
            user = db.query(User).get(telegram_id)
            if user and user.expiry_date:
                now = datetime.utcnow()
                if user.expiry_date < now:
                    user.expiry_date = now + timedelta(days=days)
                else:
                    user.expiry_date += timedelta(days=days)
                db.commit()
                flash(f"Subscription extended by {days} days.", "success")
        finally:
            db.close()
        return redirect(url_for("dashboard"))

    @app.route("/admin/ban/<int:telegram_id>", methods=["POST"])
    @login_required
    def ban_user(telegram_id):
        db = SessionLocal()
        try:
            user = db.query(User).get(telegram_id)
            if user and user.group:
                user.banned = True
                db.commit()
                bot = app.config.get('BOT_APP').bot if app.config.get('BOT_APP') else None
                if bot:
                    try:
                        run_async(bot.ban_chat_member(
                            chat_id=user.group.chat_id,
                            user_id=telegram_id
                        ))
                    except Exception:
                        pass
                flash(f"User {telegram_id} banned and kicked.", "danger")
        finally:
            db.close()
        return redirect(url_for("dashboard"))

    @app.route("/admin/unban/<int:telegram_id>", methods=["POST"])
    @login_required
    def unban_user(telegram_id):
        db = SessionLocal()
        try:
            user = db.query(User).get(telegram_id)
            if user and user.group:
                user.banned = False
                db.commit()
                bot = app.config.get('BOT_APP').bot if app.config.get('BOT_APP') else None
                if bot:
                    try:
                        run_async(bot.unban_chat_member(
                            chat_id=user.group.chat_id,
                            user_id=telegram_id
                        ))
                    except Exception:
                        pass
                flash(f"User {telegram_id} unbanned.", "success")
        finally:
            db.close()
        return redirect(url_for("dashboard"))

    return app
