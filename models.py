








from sqlalchemy import create_engine, Column, Integer, BigInteger, String, Boolean, DateTime, Text, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from config import DATABASE_URL, GROUPS_CONFIG

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

if DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://"):
    DATABASE_URL_FINAL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1).replace("postgres://", "postgresql+psycopg://", 1)
else:
    DATABASE_URL_FINAL = DATABASE_URL

engine = create_engine(DATABASE_URL_FINAL, connect_args=connect_args)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


class Group(Base):
    """Represents a Telegram channel/group available for subscription."""
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    chat_id = Column(BigInteger, unique=True, nullable=False)
    monthly_price = Column(Float, nullable=False, default=10.0)

    users = relationship("User", back_populates="group")


class User(Base):
    __tablename__ = "users"

    telegram_id = Column(BigInteger, primary_key=True)
    username = Column(String, nullable=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    group = relationship("Group", back_populates="users")
    payment_status = Column(String, default="pending")
    payment_method = Column(String, nullable=True)
    transaction_ref = Column(Text, nullable=True)
    invite_link = Column(Text, nullable=True)
    invite_link_used = Column(Boolean, default=False)
    joined = Column(Boolean, default=False)
    banned = Column(Boolean, default=False)
    expiry_date = Column(DateTime, nullable=True)
    pending_days = Column(Integer, nullable=True, default=30)  # requested duration for pending approval
    reminder_sent = Column(Boolean, default=False)  # whether the 7-day reminder was sent
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


Base.metadata.create_all(bind=engine)


# Lightweight migration: add new columns if the table already existed without them
def _ensure_columns():
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return
    existing_cols = {col["name"] for col in inspector.get_columns("users")}
    with engine.connect() as conn:
        if "pending_days" not in existing_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN pending_days INTEGER DEFAULT 30"))
            conn.commit()
        if "reminder_sent" not in existing_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN reminder_sent BOOLEAN DEFAULT FALSE"))
            conn.commit()


_ensure_columns()


def seed_groups():
    db = SessionLocal()
    try:
        for g in GROUPS_CONFIG:
            existing = db.query(Group).filter_by(chat_id=g["chat_id"]).first()
            if not existing:
                new_group = Group(
                    name=g["name"],
                    chat_id=g["chat_id"],
                    monthly_price=g["monthly_price"]
                )
                db.add(new_group)
        db.commit()
    finally:
        db.close()


seed_groups()
