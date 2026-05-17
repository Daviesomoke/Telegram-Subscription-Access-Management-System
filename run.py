







import threading
import time
from datetime import datetime
from models import SessionLocal, User, Group
from bot import setup_bot
from app import create_app

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
                        await bot_app.bot.ban_chat_member(chat_id=group.chat_id, user_id=user.telegram_id)
                        await bot_app.bot.unban_chat_member(chat_id=group.chat_id, user_id=user.telegram_id)
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

    flask_thread = threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=5000, debug=False), daemon=True)
    flask_thread.start()

    print("Bot polling started...")
    bot_app.run_polling()