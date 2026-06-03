import asyncio
import threading
import time
from datetime import datetime
from models import SessionLocal, User, Group
from bot import setup_bot
from app import create_app


async def kick_expired_user(bot, chat_id, user_id):
    """Kick and immediately unban so user can rejoin later if they renew."""
    await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
    await bot.unban_chat_member(chat_id=chat_id, user_id=user_id)
    try:
        await bot.send_message(
            chat_id=user_id,
            text=(
                "⏰ Your subscription has expired and you have been removed from the group.\n"
                "Use /start to renew your subscription."
            )
        )
    except Exception:
        pass


def expire_checker(bot_app):
    """Background thread: kicks users with expired subscriptions from their groups."""
    while True:
        db = SessionLocal()
        try:
            now = datetime.utcnow()
            expired_users = db.query(User).filter(
                User.payment_status == "approved",
                User.expiry_date <= now,
                User.banned == False,
                User.joined == True
            ).all()

            for user in expired_users:
                try:
                    group = db.query(Group).get(user.group_id) if user.group_id else None
                    if group:
                        asyncio.run(kick_expired_user(
                            bot_app.bot, group.chat_id, user.telegram_id
                        ))
                        user.joined = False
                        user.payment_status = "expired"
                        db.commit()
                except Exception as e:
                    print(f"Expire kick failed for {user.telegram_id}: {e}")
        except Exception as e:
            print(f"Expire checker error: {e}")
        finally:
            db.close()
        time.sleep(3600)


if __name__ == "__main__":
    bot_app = setup_bot()
    flask_app = create_app(bot_app)

    checker_thread = threading.Thread(target=expire_checker, args=(bot_app,), daemon=True)
    checker_thread.start()

    flask_thread = threading.Thread(
        target=lambda: flask_app.run(host="0.0.0.0", port=5000, debug=False),
        daemon=True
    )
    flask_thread.start()

    print("Bot polling started...")
    bot_app.run_polling()
