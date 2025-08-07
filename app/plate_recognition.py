import cv2
import numpy as np
import re
from typing import Optional, Tuple
import base64
from io import BytesIO
from PIL import Image

class PlateRecognitionService:
    def __init__(self):
        # Паттерны для распознавания российских номеров
        self.patterns = [
            r'[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}',  # Обычные номера
            r'[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}',  # Короткие номера
        ]
        
    def extract_text_from_image(self, image_data: bytes) -> Optional[str]:
        """Извлечение текста из изображения (заглушка для реального OCR)"""
        try:
            # В реальном проекте здесь должен быть вызов OCR библиотеки
            # Например, EasyOCR или Tesseract
            
            # Для демонстрации возвращаем случайный номер
            import random
            letters = 'АВЕКМНОРСТУХ'
            numbers = '0123456789'
            regions = ['77', '99', '177', '199', '777']
            
            plate = (
                random.choice(letters) +
                ''.join(random.choices(numbers, k=3)) +
                ''.join(random.choices(letters, k=2)) +
                random.choice(regions)
            )
            return plate
        except Exception as e:
            print(f"Ошибка извлечения текста: {e}")
            return None
    
    def recognize_plate(self, image_data: bytes) -> Optional[str]:
        """Распознавание номерного знака"""
        text = self.extract_text_from_image(image_data)
        if not text:
            return None
            
        # Очистка и валидация текста
        text = text.upper().replace(' ', '').replace('-', '')
        
        for pattern in self.patterns:
            match = re.search(pattern, text)
            if match:
                return match.group()
        
        return None
    
    def preprocess_image(self, image_data: bytes) -> bytes:
        """Предобработка изображения для лучшего распознавания"""
        try:
            # Загружаем изображение
            image_array = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            
            if image is None:
                return image_data
            
            # Применяем фильтры для улучшения качества
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Увеличиваем контрастность
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            
            # Применяем гауссово размытие для удаления шума
            blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)
            
            # Конвертируем обратно в байты
            _, buffer = cv2.imencode('.jpg', blurred)
            return buffer.tobytes()
            
        except Exception as e:
            print(f"Ошибка предобработки изображения: {e}")
            return image_data
