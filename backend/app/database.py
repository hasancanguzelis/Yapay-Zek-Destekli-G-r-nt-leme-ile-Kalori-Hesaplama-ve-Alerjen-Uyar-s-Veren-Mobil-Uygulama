from __future__ import annotations

import os
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine, Column, String, DateTime, Text, Integer, Float, Date, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from datetime import datetime, date

# Veritabanı dosyası yolu
backend_root = Path(__file__).resolve().parents[1]
db_path = backend_root / "data" / "users.db"
db_path.parent.mkdir(parents=True, exist_ok=True)

# SQLite database URL
DATABASE_URL = f"sqlite:///{db_path}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    username = Column(String, primary_key=True, index=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # Profile verileri (JSON formatında)
    profile_allergens = Column(Text, nullable=True, default=None)  # JSON array: ["gluten", "milk"]
    profile_conditions = Column(Text, nullable=True, default=None)  # JSON array: ["diabetes", "celiac"]
    # Kalori takibi için fiziksel özellikler
    profile_age = Column(Integer, nullable=True, default=None)  # int veya null
    profile_weight_kg = Column(Float, nullable=True, default=None)  # float veya null
    profile_height_cm = Column(Float, nullable=True, default=None)  # float veya null
    profile_gender = Column(String, nullable=True, default=None)  # "male", "female", "other" veya null
    profile_activity_level = Column(String, nullable=True, default=None)  # "sedentary", "light", "moderate", "active", "very_active" veya null

    def __repr__(self):
        return f"<User(username={self.username})>"


class DailyConsumption(Base):
    """Günlük kalori tüketim kayıtları."""
    __tablename__ = "daily_consumption"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String, ForeignKey("users.username"), nullable=False, index=True)
    consumption_date = Column(Date, nullable=False, default=date.today, index=True)
    
    # Besin değerleri (günlük toplam)
    calories_kcal = Column(Float, nullable=False, default=0.0)
    fat_g = Column(Float, nullable=True, default=0.0)
    carbs_g = Column(Float, nullable=True, default=0.0)
    protein_g = Column(Float, nullable=True, default=0.0)
    sugar_g = Column(Float, nullable=True, default=0.0)
    salt_g = Column(Float, nullable=True, default=0.0)
    sodium_mg = Column(Float, nullable=True, default=0.0)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship (optional, for easier access)
    user = relationship("User", backref="consumptions")

    def __repr__(self):
        return f"<DailyConsumption(username={self.username}, date={self.consumption_date}, calories={self.calories_kcal})>"


def init_db():
    """Veritabanı tablolarını oluştur."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Database session al."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

