import os
from pydantic import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:1234@localhost:5432/test"
    secret_key: str = "your-secret-key-here"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Настройки камер
    entry_camera_ip: str = "192.168.1.100"
    exit_camera_ip: str = "192.168.1.101"
    camera_username: str = "admin"
    camera_password: str = "password"
    
    # Настройки шлагбаумов
    entry_barrier_ip: str = "192.0.0.11"
    exit_barrier_ip: str = "192.0.0.12"
    barrier_username: str = "admin"
    barrier_password: str = "Deltatech2023"
    
    # Настройки тарифов
    base_price_per_hour: float = 50.0
    additional_price_per_hour: float = 30.0
    
    class Config:
        env_file = ".env"

settings = Settings()