





from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from config import DATABASE_URL, GROUPS_CONFIG

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    chat_id = Column(Integer, unique=True, nullable=False)   # Telegram chat ID
    monthly_price = Column(Float, nullable=False, default=10.0)

    users = relationship("User", back_populates="group")

class User(Base):
    __tablename__ = "users"

    telegram_id = Column(Integer, primary_key=True)
    username = Column(String, nullable=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    group = relationship("Group", back_populates="users")
    payment_status = Column(String, default="pending")   # pending, approved, rejected, expired
    payment_method = Column(String, nullable=True)
    transaction_ref = Column(Text, nullable=True)
    invite_link = Column(Text, nullable=True)
    invite_link_used = Column(Boolean, default=False)
    joined = Column(Boolean, default=False)
    banned = Column(Boolean, default=False)
    expiry_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# Seed groups from config
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