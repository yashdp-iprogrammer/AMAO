import asyncio

class PortAllocator:
    def __init__(self, start=8005):
        self._next = start
        self._lock = asyncio.Lock()

    async def get_port(self):
        async with self._lock:
            port = self._next
            self._next += 1
            return port