







import asyncio
import threading
import time
import os
from datetime import datetime, timedelta
from models import SessionLocal, User, Group
from bot import setup_bot
from app import create_app


async def kick_expired_user(bot, chat_id, user_id):
    await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
    await bot.unban_chat_member(chat_id=chat_id, user_id=user_id)
    try:
        await bot.send_message(
            chat_id=user_id,
            text=(
                "⏰ Your subscription has expired and you have been removed from the channel.\n"
                "Use /start to renew your subscription."
            )
        )
    except Exception:
        pass


async def send_reminder(bot, chat_id, channel_name, expiry_date):
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"⏳ Reminder: Your subscription to {channel_name} expires on "
                f"{expiry_date.strftime('%Y-%m-%d')} (in 7 days or less).\n\n"
                f"To avoid losing access, use /start now to renew early. "
                f"Early renewals extend your current subscription - "
                f"you won't lose any remaining days."
            )
        )
    except Exception:
        pass


def expire_checker(bot_app):
    """Background thread: kicks expired users and sends renewal reminders."""
    while True:
        db = SessionLocal()
        try:
            now = datetime.utcnow()

            # 1. Kick fully expired users
            expired_users = db.query(User).filter(
                User.payment_status == "approved",
                User.expiry_date <= now,
                User.banned == False,
                User.joined == True
            ).all()
            for user in expired_users:
                try:
                    channel = db.query(Group).get(user.group_id) if user.group_id else None
                    if channel:
                        asyncio.run(kick_expired_user(
                            bot_app.bot, channel.chat_id, user.telegram_id
                        ))
                        user.joined = False
                        user.payment_status = "expired"
                        db.commit()
                except Exception as e:
                    print(f"Expire kick failed for {user.telegram_id}: {e}")

            # 2. Send 7-day reminders for upcoming expiries
            reminder_cutoff = now + timedelta(days=7)
            soon_expiring = db.query(User).filter(
                User.payment_status == "approved",
                User.expiry_date > now,
                User.expiry_date <= reminder_cutoff,
                User.reminder_sent == False,
                User.banned == False,
            ).all()
            for user in soon_expiring:
                try:
                    channel = db.query(Group).get(user.group_id) if user.group_id else None
                    channel_name = channel.name if channel else "your channel"
                    asyncio.run(send_reminder(
                        bot_app.bot, user.telegram_id, channel_name, user.expiry_date
                    ))
                    user.reminder_sent = True
                    db.commit()
                except Exception as e:
                    print(f"Reminder failed for {user.telegram_id}: {e}")

        except Exception as e:
            print(f"Expire checker error: {e}")
        finally:
            db.close()
        time.sleep(3600)


def run_flask(flask_app, port):
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


async def main():
    bot_app = setup_bot()
    flask_app = create_app(bot_app)

    port = int(os.environ.get("PORT", 5000))
    flask_thread = threading.Thread(target=run_flask, args=(flask_app, port), daemon=True)
    flask_thread.start()
    print(f"Flask dashboard running on port {port}")

    await asyncio.sleep(2)

    checker_thread = threading.Thread(target=expire_checker, args=(bot_app,), daemon=True)
    checker_thread.start()

    print("Bot polling started...")
    async with bot_app:
        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling(
            poll_interval=1.0,
            timeout=30,
            drop_pending_updates=False,
            allowed_updates=["message", "callback_query"],
            read_timeout=30,
            write_timeout=30,
            connect_timeout=30,
            pool_timeout=30,
        )
        while True:
            await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
