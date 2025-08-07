import aiohttp
import asyncio
from typing import Optional, Tuple
import base64
from datetime import datetime
import os
from .plate_recognition import PlateRecognitionService
from .config import settings

class CameraService:
    def __init__(self):
        self.plate_recognizer = PlateRecognitionService()
        self.entry_camera_url = f"http://{settings.entry_camera_ip}"
        self.exit_camera_url = f"http://{settings.exit_camera_ip}"
        
    async def capture_image(self, camera_ip: str, is_entry: bool = True) -> Optional[Tuple[str, bytes]]:
        """Захват изображения с камеры"""
        try:
            url = f"http://{camera_ip}/ISAPI/Streaming/channels/1/picture"
            
            async with aiohttp.ClientSession() as session:
                auth = aiohttp.BasicAuth(settings.camera_username, settings.camera_password)
                
                async with session.get(url, auth=auth, timeout=10) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        
                        # Сохраняем изображение
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        camera_type = "entry" if is_entry else "exit"
                        filename = f"{camera_type}_{timestamp}.jpg"
                        filepath = os.path.join("uploads", filename)
                        
                        os.makedirs("uploads", exist_ok=True)
                        
                        with open(filepath, "wb") as f:
                            f.write(image_data)
                        
                        return filename, image_data
                    
        except Exception as e:
            print(f"Ошибка захвата изображения: {e}")
            
        return None
    
    async def capture_and_recognize(self, camera_ip: str, is_entry: bool = True) -> Optional[Tuple[str, str]]:
        """Захват изображения и распознавание номера"""
        result = await self.capture_image(camera_ip, is_entry)
        if not result:
            return None
            
        filename, image_data = result
        
        # Предобработка изображения
        processed_data = self.plate_recognizer.preprocess_image(image_data)
        
        # Распознавание номера
        plate_number = self.plate_recognizer.recognize_plate(processed_data)
        
        if plate_number:
            return plate_number, filename
        
        return None
    
    async def monitor_entry_camera(self, callback):
        """Мониторинг въездной камеры"""
        while True:
            try:
                result = await self.capture_and_recognize(settings.entry_camera_ip, True)
                if result:
                    plate_number, filename = result
                    await callback(plate_number, filename, True)
                
                await asyncio.sleep(5)  # Проверяем каждые 5 секунд
                
            except Exception as e:
                print(f"Ошибка мониторинга въездной камеры: {e}")
                await asyncio.sleep(10)
    
    async def monitor_exit_camera(self, callback):
        """Мониторинг выездной камеры"""
        while True:
            try:
                result = await self.capture_and_recognize(settings.exit_camera_ip, False)
                if result:
                    plate_number, filename = result
                    await callback(plate_number, filename, False)
                
                await asyncio.sleep(5)  # Проверяем каждые 5 секунд
                
            except Exception as e:
                print(f"Ошибка мониторинга выездной камеры: {e}")
                await asyncio.sleep(10)