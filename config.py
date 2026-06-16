import os
import json
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

# Render gives DATABASE_URL starting with "postgres://" but SQLAlchemy 2.x needs "postgresql://"
_raw_db_url = os.getenv("DATABASE_URL", "sqlite:///subscriptions.db")
DATABASE_URL = _raw_db_url.replace("postgres://", "postgresql://", 1)

# Parse groups config
groups_json = os.getenv("GROUPS_CONFIG", "[]")
GROUPS_CONFIG = json.loads(groups_json)

# Duration multipliers
multipliers_json = os.getenv("DURATION_MULTIPLIERS", '{"1":1,"3":2.7,"6":5,"12":9}')
DURATION_MULTIPLIERS = json.loads(multipliers_json)

# Payment instructions texts
M_PESA_PHONE = os.getenv("M_PESA_PHONE", "+254700000000")
M_PESA_NAME = os.getenv("M_PESA_NAME", "Your Name")
SKRILL_EMAIL = os.getenv("SKRILL_EMAIL", "your@skrill.com")
NETELLER_EMAIL = os.getenv("NETELLER_EMAIL", "your@neteller.com")
USDT_TRC20_ADDRESS = os.getenv("USDT_TRC20_ADDRESS", "TRX1234567890")
