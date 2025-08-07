import qrcode
from io import BytesIO
import base64
from datetime import datetime, timedelta
from typing import Optional
from .models import VehicleEntry, ParkingSettings
from .config import settings

class PaymentService:
    def calculate_parking_fee(self, entry_time: datetime, exit_time: datetime, 
                            parking_settings: ParkingSettings) -> float:
        """Расчет стоимости парковки"""
        if not entry_time or not exit_time:
            return 0.0
            
        # Время парковки в минутах
        parking_duration = (exit_time - entry_time).total_seconds() / 60
        
        # Бесплатные минуты
        if parking_duration <= parking_settings.free_minutes:
            return 0.0
        
        # Платное время в часах (округление вверх)
        chargeable_hours = max(1, int((parking_duration - parking_settings.free_minutes + 59) // 60))
        
        # Первый час по базовой цене, остальные по дополнительной
        if chargeable_hours == 1:
            return parking_settings.base_price_per_hour
        else:
            return (parking_settings.base_price_per_hour + 
                   (chargeable_hours - 1) * parking_settings.additional_price_per_hour)
    
    def generate_qr_code(self, vehicle_entry: VehicleEntry, amount: float) -> str:
        """Генерация QR-кода для оплаты"""
        try:
            # Данные для QR-кода (в реальности здесь должны быть данные платежной системы)
            payment_data = {
                "vehicle_id": vehicle_entry.id,
                "plate_number": vehicle_entry.plate_number,
                "amount": amount,
                "timestamp": datetime.now().isoformat()
            }
            
            # Создаем строку для QR-кода
            qr_data = f"PAY:{vehicle_entry.id}:{amount}:{vehicle_entry.plate_number}"
            
            # Генерируем QR-код
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(qr_data)
            qr.make(fit=True)
            
            # Создаем изображение
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Конвертируем в base64
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            qr_image_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            return f"data:image/png;base64,{qr_image_base64}"
            
        except Exception as e:
            print(f"Ошибка генерации QR-кода: {e}")
            return ""
    
    def verify_payment(self, payment_data: str) -> bool:
        """Проверка оплаты (заглушка)"""
        # В реальном проекте здесь должна быть интеграция с платежной системой
        # Для демонстрации возвращаем True
        return True