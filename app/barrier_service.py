import aiohttp
from typing import Literal
from .config import settings

class BarrierService:
    def __init__(self):
        self.entry_barrier_url = f"http://{settings.entry_barrier_ip}/ISAPI/Parking/channels/1/barrierGate"
        self.exit_barrier_url = f"http://{settings.exit_barrier_ip}/ISAPI/Parking/channels/1/barrierGate"
        
    async def control_barrier(self, action: Literal["open", "close"], is_entry: bool = True) -> bool:
        """Управление шлагбаумом"""
        try:
            url = self.entry_barrier_url if is_entry else self.exit_barrier_url
            
            xml_body = (
                '<?xml version="1.0" encoding="utf-8"?>'
                f"<BarrierGate><ctrlMode>{action}</ctrlMode></BarrierGate>"
            )
            
            auth = aiohttp.BasicAuth(settings.barrier_username, settings.barrier_password)
            headers = {"Content-Type": "application/xml"}
            
            async with aiohttp.ClientSession() as session:
                async with session.put(
                    url,
                    auth=auth,
                    headers=headers,
                    data=xml_body.encode('utf-8'),
                    timeout=5
                ) as response:
                    success = response.status == 200
                    print(f"Шлагбаум {'въезд' if is_entry else 'выезд'} {action}: {response.status}")
                    return success
                    
        except Exception as e:
            print(f"Ошибка управления шлагбаумом: {e}")
            return False
    
    async def open_entry_barrier(self) -> bool:
        """Открыть въездной шлагбаум"""
        return await self.control_barrier("open", True)
    
    async def close_entry_barrier(self) -> bool:
        """Закрыть въездной шлагбаум"""
        return await self.control_barrier("close", True)
    
    async def open_exit_barrier(self) -> bool:
        """Открыть выездной шлагбаум"""
        return await self.control_barrier("open", False)
    
    async def close_exit_barrier(self) -> bool:
        """Закрыть выездной шлагбаум"""
        return await self.control_barrier("close", False)