import asyncio
import inspect
import functools


class Socket:

    def __init__(self, host, port, eol=b'\n'):
        self._host = host
        self._port = port
        self._eol = eol
        self._reader = None
        self._writer = None

    async def _ensure_connected(self):
        if not self.connected:
            await self.open()

    async def open(self):
        self._reader, self._writer = await asyncio.open_connection(
            self._host, self._port)

    @property
    def connected(self):
        return False if self._reader is None else not self._reader.at_eof()

    async def read(self, n=-1):
        await self._ensure_connected()
        return await self._reader.read(n)

    async def readline(self):
        await self._ensure_connected()
        return await self._reader.readline()

    async def readlines(self, n):
        await self._ensure_connected()
        for i in range(n):
            yield await self._reader.readline()

    async def readexactly(self, n):
        await self._ensure_connected()
        return await self._reader.readexactly(n)

    async def readuntil(self, separator=b'\n'):
        await self._ensure_connected()
        return await self._reader.readuntil(separator)

    async def write(self, data):
        await self._ensure_connected()
        self._writer.write(data)
        await self._writer.drain()

    async def writelines(self, lines):
        self._writer.writelines(lines)
        await self._writer.drain()

    async def write_readline(self, data):
        await self._ensure_connected()
        self._writer.write(data)
        await self._writer.drain()
        return await self._reader.readline()

    async def write_readline(self, data):
        await self._ensure_connected()
        self._writer.write(data)
        await self._writer.drain()
        return await self._reader.readline()

    async def write_readlines(self, data, n):
        await self._ensure_connected()
        self._writer.write(data)
        await self._writer.drain()
        for i in range(n):
            yield await self._reader.readline()

    async def writelines_readlines(self, lines, n=None):
        await self._ensure_connected()
        if n is None:
            n = len(lines)
        self._writer.writelines(lines)
        await self._writer.drain()
        for i in range(n):
            yield await self._reader.readline()

    async def close(self):
        self._writer.close()
        await self._writer.wait_closed()
