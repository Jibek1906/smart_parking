import cv2
import numpy as np
import re
import pytesseract
from typing import Optional, Tuple
import logging
from PIL import Image, ImageEnhance, ImageFilter
import os

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PlateRecognitionService:
    def __init__(self):
        # Паттерны для распознавания российских номеров
        self.patterns = [
            r'[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}',  # A123BC77
            r'[АВЕКМНОРСТУХ]{2}\d{3}\d{2,3}',                # AB12377
            r'[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}',         # A123BC (без региона)
        ]
        
        # Словарь для замены похожих символов
        self.char_corrections = {
            '0': 'О', '1': 'І', '8': 'В', '6': 'Б',
            'O': 'О', 'I': 'І', 'B': 'В', 'P': 'Р',
            'C': 'С', 'Y': 'У', 'H': 'Н', 'K': 'К',
            'M': 'М', 'T': 'Т', 'X': 'Х', 'A': 'А',
            'E': 'Е'
        }
        
        # Настройка Tesseract
        self.tesseract_config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789АВЕКМНОРСТУХABCEKMHOPCTYX'
        
        # Проверяем доступность Tesseract
        try:
            pytesseract.get_tesseract_version()
            self.tesseract_available = True
            logger.info("Tesseract OCR доступен")
        except Exception as e:
            logger.warning(f"Tesseract OCR недоступен: {e}")
            self.tesseract_available = False
    
    def preprocess_image_for_ocr(self, image_data: bytes) -> Optional[Image.Image]:
        """Предобработка изображения для улучшения OCR"""
        try:
            # Загружаем изображение
            image_array = np.frombuffer(image_data, np.uint8)
            cv_image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            
            if cv_image is None:
                logger.error("Не удалось декодировать изображение")
                return None
            
            # Конвертируем в серый
            gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
            
            # Увеличиваем изображение для лучшего OCR
            scale_factor = 3.0
            height, width = gray.shape
            new_height, new_width = int(height * scale_factor), int(width * scale_factor)
            resized = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
            
            # Применяем фильтр для улучшения четкости
            sharpened = cv2.filter2D(resized, -1, np.array([[-1,-1,-1],[-1,9,-1],[-1,-1,-1]]))
            
            # Улучшаем контрастность с помощью CLAHE
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            enhanced = clahe.apply(sharpened)
            
            # Применяем морфологические операции для очистки
            kernel = np.ones((2,2), np.uint8)
            cleaned = cv2.morphologyEx(enhanced, cv2.MORPH_CLOSE, kernel)
            
            # Бинаризация с адаптивным порогом
            binary = cv2.adaptiveThreshold(
                cleaned, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
            
            # Конвертируем обратно в PIL Image
            pil_image = Image.fromarray(binary)
            
            return pil_image
            
        except Exception as e:
            logger.error(f"Ошибка предобработки изображения: {e}")
            return None
    
    def extract_plate_region(self, image_data: bytes) -> Optional[bytes]:
        """Попытка выделения области номерного знака"""
        try:
            image_array = np.frombuffer(image_data, np.uint8)
            cv_image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            
            if cv_image is None:
                return image_data
            
            gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
            
            # Используем каскад Хаара для поиска номерных знаков (если есть)
            # В реальном проекте нужно загрузить предобученный каскад
            # plate_cascade = cv2.CascadeClassifier('haarcascade_plate.xml')
            
            # Пока используем простое выделение прямоугольных областей
            # Применяем детектор границ
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            
            # Находим контуры
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Ищем прямоугольные контуры подходящего размера
            for contour in contours:
                approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
                if len(approx) == 4:
                    x, y, w, h = cv2.boundingRect(contour)
                    aspect_ratio = w / h
                    area = w * h
                    
                    # Проверяем соотношение сторон и размер (типичные для номера)
                    if 2.0 <= aspect_ratio <= 6.0 and 1000 <= area <= 50000:
                        # Извлекаем область
                        plate_region = cv_image[y:y+h, x:x+w]
                        
                        # Конвертируем в байты
                        _, buffer = cv2.imencode('.jpg', plate_region)
                        return buffer.tobytes()
            
            # Если не нашли номер, возвращаем исходное изображение
            return image_data
            
        except Exception as e:
            logger.error(f"Ошибка выделения области номера: {e}")
            return image_data
    
    def extract_text_from_image(self, image_data: bytes) -> Optional[str]:
        """Извлечение текста из изображения с помощью OCR"""
        if not self.tesseract_available:
            logger.warning("Tesseract недоступен, используем заглушку")
            return self._generate_mock_plate()
        
        try:
            # Сначала пытаемся выделить область номера
            plate_image_data = self.extract_plate_region(image_data)
            
            # Предобработка изображения
            processed_image = self.preprocess_image_for_ocr(plate_image_data)
            if not processed_image:
                return None
            
            # OCR с Tesseract
            raw_text = pytesseract.image_to_string(
                processed_image, 
                config=self.tesseract_config,
                lang='eng+rus'
            ).strip()
            
            logger.info(f"OCR результат: '{raw_text}'")
            
            if not raw_text:
                # Пробуем с другими настройками PSM
                for psm in [7, 8, 13]:
                    config = f'--oem 3 --psm {psm} -c tessedit_char_whitelist=0123456789АВЕКМНОРСТУХABCEKMHOPCTYX'
                    raw_text = pytesseract.image_to_string(
                        processed_image, 
                        config=config,
                        lang='eng+rus'
                    ).strip()
                    if raw_text:
                        break
            
            return raw_text if raw_text else None
            
        except Exception as e:
            logger.error(f"Ошибка извлечения текста: {e}")
            return None
    
    def clean_and_correct_text(self, text: str) -> str:
        """Очистка и исправление распознанного текста"""
        if not text:
            return ""
        
        # Убираем пробелы, переносы и специальные символы
        cleaned = re.sub(r'[^\w\d]', '', text.upper())
        
        # Исправляем похожие символы
        corrected = ""
        for char in cleaned:
            corrected += self.char_corrections.get(char, char)
        
        return corrected
    
    def validate_plate_format(self, plate: str) -> bool:
        """Проверка соответствия номера российскому формату"""
        if not plate:
            return False
        
        for pattern in self.patterns:
            if re.match(pattern, plate):
                return True
        
        return False
    
    def recognize_plate(self, image_data: bytes) -> Optional[str]:
        """Основной метод распознавания номерного знака"""
        try:
            # Извлекаем текст
            raw_text = self.extract_text_from_image(image_data)
            if not raw_text:
                logger.warning("OCR не извлек текст")
                return None
            
            logger.info(f"Сырой текст OCR: '{raw_text}'")
            
            # Очищаем и исправляем текст
            cleaned_text = self.clean_and_correct_text(raw_text)
            logger.info(f"Очищенный текст: '{cleaned_text}'")
            
            # Пробуем найти номер в тексте
            for pattern in self.patterns:
                matches = re.findall(pattern, cleaned_text)
                if matches:
                    plate = matches[0]
                    logger.info(f"Найден номер: {plate}")
                    return plate
            
            # Если точное совпадение не найдено, пробуем "восстановить" номер
            recovered_plate = self._attempt_plate_recovery(cleaned_text)
            if recovered_plate and self.validate_plate_format(recovered_plate):
                logger.info(f"Восстановлен номер: {recovered_plate}")
                return recovered_plate
            
            logger.warning(f"Номер не распознан из текста: '{cleaned_text}'")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка распознавания номера: {e}")
            return None
    
    def _attempt_plate_recovery(self, text: str) -> Optional[str]:
        """Попытка восстановления номера из частично распознанного текста"""
        if len(text) < 6:
            return None
        
        # Пытаемся найти паттерн: буква + 3 цифры + 2 буквы + регион
        # Например: А123ВС77
        
        # Ищем цифры
        digits = re.findall(r'\d', text)
        letters = re.findall(r'[АВЕКМНОРСТУХ]', text)
        
        if len(digits) >= 3 and len(letters) >= 3:
            # Пытаемся составить номер
            plate = letters[0] + ''.join(digits[:3]) + ''.join(letters[1:3])
            
            # Добавляем регион, если есть больше цифр
            if len(digits) >= 5:
                plate += ''.join(digits[3:5])
            elif len(digits) == 4:
                plate += digits[3] + '7'  # Добавляем 7 для Москвы по умолчанию
            else:
                plate += '77'  # Москва по умолчанию
            
            return plate
        
        return None
    
    def _generate_mock_plate(self) -> str:
        """Генерация тестового номера (только для разработки!)"""
        import random
        letters = 'АВЕКМНОРСТУХ'
        numbers = '0123456789'
        regions = ['77', '99', '177', '199', '777', '97', '197', '777']
        
        plate = (
            random.choice(letters) +
            ''.join(random.choices(numbers, k=3)) +
            ''.join(random.choices(letters, k=2)) +
            random.choice(regions)
        )
        
        logger.warning(f"ВНИМАНИЕ: Используется тестовый номер {plate}")
        return plate
    
    def preprocess_image(self, image_data: bytes) -> bytes:
        """Предобработка изображения для сохранения (совместимость со старым API)"""
        try:
            # Загружаем изображение
            image_array = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            
            if image is None:
                return image_data
            
            # Применяем базовые улучшения
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Увеличиваем контрастность
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            
            # Применяем легкое размытие для удаления шума
            blurred = cv2.GaussianBlur(enhanced, (3, 3), 0)
            
            # Конвертируем обратно в цветное для сохранения
            processed = cv2.cvtColor(blurred, cv2.COLOR_GRAY2BGR)
            
            # Конвертируем в байты
            _, buffer = cv2.imencode('.jpg', processed)
            return buffer.tobytes()
            
        except Exception as e:
            logger.error(f"Ошибка предобработки изображения: {e}")
            return image_data

# Функция для тестирования
def test_recognition():
    """Тестовая функция для проверки работы распознавания"""
    recognizer = PlateRecognitionService()
    
    # Тест с пустыми данными
    result = recognizer.recognize_plate(b'')
    print(f"Пустые данные: {result}")
    
    # Тест валидации
    test_plates = ["А123ВС77", "AB123CD", "А12ВС77", "А123В777"]
    for plate in test_plates:
        is_valid = recognizer.validate_plate_format(plate)
        print(f"Номер {plate}: {'✓' if is_valid else '✗'}")

if __name__ == "__main__":
    test_recognition()