from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from datetime import datetime, timedelta
from typing import Optional, List
from . import models, schemas

# Vehicle Entry CRUD
def create_vehicle_entry(db: Session, entry: schemas.VehicleEntryCreate) -> models.VehicleEntry:
    db_entry = models.VehicleEntry(**entry.dict())
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry

def get_vehicle_entry(db: Session, entry_id: int) -> Optional[models.VehicleEntry]:
    return db.query(models.VehicleEntry).filter(models.VehicleEntry.id == entry_id).first()

def get_vehicle_entry_by_plate(db: Session, plate_number: str, 
                              exclude_exited: bool = True) -> Optional[models.VehicleEntry]:
    query = db.query(models.VehicleEntry).filter(models.VehicleEntry.plate_number == plate_number)
    
    if exclude_exited:
        query = query.filter(models.VehicleEntry.exit_time.is_(None))
    
    return query.order_by(desc(models.VehicleEntry.entry_time)).first()

def get_vehicle_entries(db: Session, skip: int = 0, limit: int = 100) -> List[models.VehicleEntry]:
    return db.query(models.VehicleEntry).order_by(
        desc(models.VehicleEntry.entry_time)
    ).offset(skip).limit(limit).all()

def update_vehicle_entry(db: Session, entry_id: int, 
                        entry_update: schemas.VehicleEntryUpdate) -> Optional[models.VehicleEntry]:
    db_entry = db.query(models.VehicleEntry).filter(models.VehicleEntry.id == entry_id).first()
    if db_entry:
        update_data = entry_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_entry, key, value)
        db.commit()
        db.refresh(db_entry)
    return db_entry

def mark_as_paid(db: Session, entry_id: int) -> Optional[models.VehicleEntry]:
    db_entry = db.query(models.VehicleEntry).filter(models.VehicleEntry.id == entry_id).first()
    if db_entry:
        db_entry.paid = True
        db.commit()
        db.refresh(db_entry)
    return db_entry

# Parking Settings CRUD
def get_parking_settings(db: Session) -> Optional[models.ParkingSettings]:
    return db.query(models.ParkingSettings).first()

def create_parking_settings(db: Session, settings: schemas.ParkingSettingsUpdate) -> models.ParkingSettings:
    db_settings = models.ParkingSettings(**settings.dict())
    db.add(db_settings)
    db.commit()
    db.refresh(db_settings)
    return db_settings

def update_parking_settings(db: Session, 
                           settings_update: schemas.ParkingSettingsUpdate) -> Optional[models.ParkingSettings]:
    db_settings = db.query(models.ParkingSettings).first()
    if db_settings:
        update_data = settings_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_settings, key, value)
        db.commit()
        db.refresh(db_settings)
    else:
        # Создаем настройки, если их нет
        db_settings = create_parking_settings(db, settings_update)
    return db_settings

def get_current_parked_vehicles(db: Session) -> List[models.VehicleEntry]:
    """Получить список машин, находящихся на парковке"""
    return db.query(models.VehicleEntry).filter(
        models.VehicleEntry.exit_time.is_(None)
    ).order_by(desc(models.VehicleEntry.entry_time)).all()

def get_unpaid_vehicles(db: Session) -> List[models.VehicleEntry]:
    """Получить список неоплаченных выездов"""
    return db.query(models.VehicleEntry).filter(
        models.VehicleEntry.exit_time.isnot(None),
        models.VehicleEntry.paid == False,
        models.VehicleEntry.parking_fee > 0
    ).order_by(desc(models.VehicleEntry.exit_time)).all()