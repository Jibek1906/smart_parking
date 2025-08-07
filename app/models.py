from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, Text, LargeBinary
from sqlalchemy.sql import func
from .database import Base

class VehicleEntry(Base):
    __tablename__ = "vehicle_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    parking_spot = Column(Integer, nullable=True)
    plate_number = Column(String(20), index=True, nullable=False)
    entry_time = Column(DateTime, server_default=func.now())
    exit_time = Column(DateTime, nullable=True)
    entry_image = Column(String(255), nullable=True)
    exit_image = Column(String(255), nullable=True)
    parking_fee = Column(Float, default=0.0)
    paid = Column(Boolean, default=False)
    payment_qr = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class ParkingSettings(Base):
    __tablename__ = "parking_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    base_price_per_hour = Column(Float, default=50.0)
    additional_price_per_hour = Column(Float, default=30.0)
    free_minutes = Column(Integer, default=15)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class AdminUser(Base):
    __tablename__ = "admin_users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    hashed_password = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())