from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Form, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.requests import Request
from sqlalchemy.orm import Session
from datetime import datetime
import asyncio
from typing import List, Optional
import os
import json

from app import crud, models, schemas
from .database import SessionLocal, engine, get_db
from .camera_service import CameraService
from .barrier_service import BarrierService
from .payment_service import PaymentService

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart Parking System", version="1.0.0")

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
templates = Jinja2Templates(directory="templates")


camera_service = CameraService()
barrier_service = BarrierService()
payment_service = PaymentService()

monitoring_active = False

@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске"""
    # Создаем директории
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("static/css", exist_ok=True)
    os.makedirs("static/js", exist_ok=True)
    
    # Создаем базовые настройки парковки
    db = SessionLocal()
    try:
        settings = crud.get_parking_settings(db)
        if not settings:
            default_settings = schemas.ParkingSettingsUpdate(
                base_price_per_hour=50.0,
                additional_price_per_hour=30.0,
                free_minutes=15
            )
            crud.create_parking_settings(db, default_settings)
    finally:
        db.close()
    
    # Запускаем мониторинг камер
    global monitoring_active
    monitoring_active = True
    asyncio.create_task(start_camera_monitoring())

@app.on_event("shutdown")
async def shutdown_event():
    """Остановка мониторинга"""
    global monitoring_active
    monitoring_active = False

async def start_camera_monitoring():
    """Запуск мониторинга камер"""
    async def handle_vehicle_detection(plate_number: str, image_filename: str, is_entry: bool):
        """Обработка обнаружения автомобиля"""
        db = SessionLocal()
        try:
            if is_entry:
                await handle_vehicle_entry(db, plate_number, image_filename)
            else:
                await handle_vehicle_exit(db, plate_number, image_filename)
        finally:
            db.close()
    
    # Запускаем мониторинг обеих камер
    await asyncio.gather(
        camera_service.monitor_entry_camera(handle_vehicle_detection),
        camera_service.monitor_exit_camera(handle_vehicle_detection)
    )

async def handle_vehicle_entry(db: Session, plate_number: str, image_filename: str):
    """Обработка въезда автомобиля"""
    try:
        # Проверяем, нет ли уже записи о въезде без выезда
        existing_entry = crud.get_vehicle_entry_by_plate(db, plate_number, exclude_exited=True)
        
        if existing_entry:
            print(f"Автомобиль {plate_number} уже на парковке")
            return
        
        # Создаем запись о въезде
        entry_data = schemas.VehicleEntryCreate(
            plate_number=plate_number,
            entry_image=image_filename
        )
        
        vehicle_entry = crud.create_vehicle_entry(db, entry_data)
        print(f"Въезд зафиксирован: {plate_number} в {vehicle_entry.entry_time}")
        
        # Открываем шлагбаум
        await barrier_service.open_entry_barrier()
        await asyncio.sleep(5)  # Держим открытым 5 секунд
        await barrier_service.close_entry_barrier()
        
    except Exception as e:
        print(f"Ошибка при обработке въезда: {e}")

async def handle_vehicle_exit(db: Session, plate_number: str, image_filename: str):
    """Обработка выезда автомобиля"""
    try:
        # Ищем запись о въезде без выезда
        vehicle_entry = crud.get_vehicle_entry_by_plate(db, plate_number, exclude_exited=True)
        
        if not vehicle_entry:
            print(f"Не найдена запись о въезде для {plate_number}")
            return
        
        # Получаем настройки парковки
        parking_settings = crud.get_parking_settings(db)
        if not parking_settings:
            parking_settings = crud.create_parking_settings(
                db, 
                schemas.ParkingSettingsUpdate(
                    base_price_per_hour=50.0,
                    additional_price_per_hour=30.0,
                    free_minutes=15
                )
            )
        
        # Обновляем запись с временем выезда
        exit_time = datetime.now()
        parking_fee = payment_service.calculate_parking_fee(
            vehicle_entry.entry_time, 
            exit_time, 
            parking_settings
        )
        
        update_data = schemas.VehicleEntryUpdate(
            exit_time=exit_time,
            exit_image=image_filename,
            parking_fee=parking_fee
        )
        
        updated_entry = crud.update_vehicle_entry(db, vehicle_entry.id, update_data)
        
        if parking_fee > 0:
            # Генерируем QR-код для оплаты
            qr_code = payment_service.generate_qr_code(updated_entry, parking_fee)
            updated_entry.payment_qr = qr_code
            db.commit()
            
            print(f"Выезд {plate_number}: требуется оплата {parking_fee} руб.")
        else:
            # Бесплатная парковка - открываем шлагбаум
            await barrier_service.open_exit_barrier()
            await asyncio.sleep(5)
            await barrier_service.close_exit_barrier()
            
            # Отмечаем как оплаченное
            crud.mark_as_paid(db, vehicle_entry.id)
            print(f"Бесплатный выезд: {plate_number}")
        
    except Exception as e:
        print(f"Ошибка при обработке выезда: {e}")

# ==================== API ENDPOINTS ====================

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, db: Session = Depends(get_db)):
    """Главная страница"""
    current_vehicles = crud.get_current_parked_vehicles(db)
    unpaid_vehicles = crud.get_unpaid_vehicles(db)
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "current_vehicles": current_vehicles,
        "unpaid_vehicles": unpaid_vehicles
    })

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, db: Session = Depends(get_db)):
    """Страница администратора"""
    settings = crud.get_parking_settings(db)
    recent_entries = crud.get_vehicle_entries(db, limit=50)
    
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "settings": settings,
        "recent_entries": recent_entries
    })

@app.get("/payment/{vehicle_id}", response_class=HTMLResponse)
async def payment_page(request: Request, vehicle_id: int, db: Session = Depends(get_db)):
    """Страница оплаты"""
    vehicle_entry = crud.get_vehicle_entry(db, vehicle_id)
    if not vehicle_entry:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    
    return templates.TemplateResponse("payment.html", {
        "request": request,
        "vehicle": vehicle_entry
    })

# API для управления записями
@app.get("/api/vehicles/", response_model=List[schemas.VehicleEntryResponse])
def get_vehicles(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Получить список записей о транспортных средствах"""
    return crud.get_vehicle_entries(db, skip=skip, limit=limit)

@app.get("/api/vehicles/{vehicle_id}", response_model=schemas.VehicleEntryResponse)
def get_vehicle(vehicle_id: int, db: Session = Depends(get_db)):
    """Получить запись о транспортном средстве"""
    vehicle = crud.get_vehicle_entry(db, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    return vehicle

@app.get("/api/vehicles/parked/", response_model=List[schemas.VehicleEntryResponse])
def get_parked_vehicles(db: Session = Depends(get_db)):
    """Получить список припаркованных автомобилей"""
    return crud.get_current_parked_vehicles(db)

@app.get("/api/vehicles/unpaid/", response_model=List[schemas.VehicleEntryResponse])
def get_unpaid_vehicles(db: Session = Depends(get_db)):
    """Получить список неоплаченных выездов"""
    return crud.get_unpaid_vehicles(db)

# API для настроек парковки
@app.get("/api/settings/", response_model=schemas.ParkingSettingsResponse)
def get_settings(db: Session = Depends(get_db)):
    """Получить настройки парковки"""
    settings = crud.get_parking_settings(db)
    if not settings:
        raise HTTPException(status_code=404, detail="Настройки не найдены")
    return settings

@app.put("/api/settings/", response_model=schemas.ParkingSettingsResponse)
def update_settings(settings: schemas.ParkingSettingsUpdate, db: Session = Depends(get_db)):
    """Обновить настройки парковки"""
    updated_settings = crud.update_parking_settings(db, settings)
    if not updated_settings:
        raise HTTPException(status_code=404, detail="Не удалось обновить настройки")
    return updated_settings

# API для оплаты
@app.post("/api/payment/")
async def process_payment(payment: schemas.PaymentRequest, db: Session = Depends(get_db)):
    """Обработка оплаты"""
    vehicle_entry = crud.get_vehicle_entry(db, payment.vehicle_id)
    if not vehicle_entry:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    
    if vehicle_entry.paid:
        raise HTTPException(status_code=400, detail="Уже оплачено")
    
    # В реальном проекте здесь должна быть интеграция с платежной системой
    payment_verified = payment_service.verify_payment(f"{payment.vehicle_id}:{payment.amount}")
    
    if payment_verified:
        # Отмечаем как оплаченное
        crud.mark_as_paid(db, payment.vehicle_id)
        
        # Открываем шлагбаум
        await barrier_service.open_exit_barrier()
        await asyncio.sleep(5)
        await barrier_service.close_exit_barrier()
        
        return {"status": "success", "message": "Оплата прошла успешно"}
    else:
        raise HTTPException(status_code=400, detail="Ошибка оплаты")

# API для ручного управления шлагбаумами
@app.post("/api/barrier/entry/{action}")
async def control_entry_barrier(action: str):
    """Управление въездным шлагбаумом"""
    if action not in ["open", "close"]:
        raise HTTPException(status_code=400, detail="Неверное действие")
    
    success = await barrier_service.control_barrier(action, is_entry=True)
    return {"success": success, "action": action, "barrier": "entry"}

@app.post("/api/barrier/exit/{action}")
async def control_exit_barrier(action: str):
    """Управление выездным шлагбаумом"""
    if action not in ["open", "close"]:
        raise HTTPException(status_code=400, detail="Неверное действие")
    
    success = await barrier_service.control_barrier(action, is_entry=False)
    return {"success": success, "action": action, "barrier": "exit"}

# API для ручного добавления/обновления записей
@app.post("/api/vehicles/", response_model=schemas.VehicleEntryResponse)
def create_vehicle_entry_manual(entry: schemas.VehicleEntryCreate, db: Session = Depends(get_db)):
    """Ручное создание записи о въезде"""
    return crud.create_vehicle_entry(db, entry)

@app.put("/api/vehicles/{vehicle_id}", response_model=schemas.VehicleEntryResponse)
def update_vehicle_entry_manual(vehicle_id: int, entry_update: schemas.VehicleEntryUpdate, 
                               db: Session = Depends(get_db)):
    """Ручное обновление записи"""
    updated_entry = crud.update_vehicle_entry(db, vehicle_id, entry_update)
    if not updated_entry:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    return updated_entry

# API для загрузки изображений
@app.post("/api/upload/")
async def upload_image(file: UploadFile = File(...)):
    """Загрузка изображения"""
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Файл должен быть изображением")
    
    # Создаем уникальное имя файла
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{file.filename}"
    filepath = os.path.join("uploads", filename)
    
    # Сохраняем файл
    with open(filepath, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    return {"filename": filename, "path": f"/uploads/{filename}"}

@app.post("/api/camera/capture/{camera_type}")
async def capture_camera_image(camera_type: str, db: Session = Depends(get_db)):
    """Ручной захват изображения с камеры"""
    if camera_type not in ["entry", "exit"]:
        raise HTTPException(status_code=400, detail="Неверный тип камеры")

    is_entry = camera_type == "entry"
    
    # Получаем настройки парковки из БД
    settings = crud.get_parking_settings(db)
    if not settings:
        raise HTTPException(status_code=404, detail="Настройки не найдены")
    
    camera_ip = settings.entry_camera_ip if is_entry else settings.exit_camera_ip

    result = await camera_service.capture_and_recognize(camera_ip, is_entry)

    if result:
        plate_number, filename = result
        return {
            "success": True,
            "plate_number": plate_number,
            "image": f"/uploads/{filename}"
        }
    else:
        return {"success": False, "message": "Не удалось захватить изображение"}
    
    # API для коррекции номеров
@app.post("/api/plates/correct")
async def correct_plate(data: dict, db: Session = Depends(get_db)):
    plate = data.get('plate')
    camera_type = data.get('camera')
    
    # Логика обновления номера в БД
    return {"status": "Номер обновлен"}

# API для получения статуса парковки
@app.get("/api/parking/status")
async def get_parking_status(db: Session = Depends(get_db)):
    spots = []
    for i in range(1, 61):
        # Проверка занятости места (заглушка)
        occupied = i % 4 == 0  # Пример: каждое 4-е место занято
        spots.append({
            "number": i,
            "occupied": occupied,
            "plate": f"А{100 + i}БВ77" if occupied else None
        })
    return {"spots": spots}

# Аварийная остановка
@app.post("/api/system/emergency")
async def emergency_stop():
    # Закрыть все шлагбаумы
    await barrier_service.close_entry_barrier()
    await barrier_service.close_exit_barrier()
    return {"status": "Система остановлена"}

@app.get("/cameras", response_class=HTMLResponse)
async def camera_page(request: Request):
    return templates.TemplateResponse("cameras.html", {"request": request})

@app.get("/parking", response_class=HTMLResponse)
async def parking_page(request: Request, db: Session = Depends(get_db)):
    vehicles = crud.get_vehicle_entries(db, limit=200)
    return templates.TemplateResponse("parking.html", {
        "request": request,
        "vehicles": vehicles
    })

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    settings = crud.get_parking_settings(db)
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "settings": settings
    })
