import asyncio
import inspect
import functools


class TCP:

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


def proxy_for(klass, resolve_futures=False):
    def coroutine_threadsafe(coro, resolve_future=False):
        @functools.wraps(coro)
        def wrapper(self, *args, **kwargs):
            future = asyncio.run_coroutine_threadsafe(
                coro(self, *args, **kwargs), self.loop).result()
            return future.result() if resolve_future else future
        return wrapper

    def function_threadsafe(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            f = functools.partial(func, *args, **kwargs)
            return self.loop.call_soon_threadsafe(f)

    class Proxy:
        def __init__(self, ref, loop):
            self.ref = ref
            self.loop = loop

    for name in dir(klass):
        if name.startswith('_'):
            continue
        member = getattr(klass, name)
        if inspect.iscoroutinefunction(member):
            member = coroutine_threadsafe(member, resolve_futures)
        elif callable(member):
            member = function_threadsafe(member)
        setattr(Proxy, name, member)
    return Proxy


Proxy = proxy_for(TCP)



async def main():
    import logging
    logging.basicConfig(level=logging.DEBUG)
    asyncio.get_event_loop().set_debug(True)
    tcp = TCP('localhost', 12345)
    print(await tcp.write_readline(b'*idn?\n'))
    await asyncio.sleep(10)
    print(await tcp.write_readline(b'*idn?\n'))


class BaseProxy:

    def __init__(self, ref):
        self._ref = ref


import threading
class SynchronousEventLoop(threading.Thread):

    def __init__(self, name='AIOTH', loop=None):
        self.loop = loop or asyncio.new_event_loop()
        self.proxies = {}
        super().__init__(name=name)
        self.daemon = True

    def run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def stop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)

    def call_soon(self, func, *args, **kwargs):
        f = functools.partial(func, *args, **kwargs)
        return self.loop.call_soon_threadsafe(f)

    def run_coroutine(self, coro, wait=False):
         future = asyncio.run_coroutine_threadsafe(coro, self.loop)
         return future.result() if wait else future

    def _create_coroutine_threadsafe(self, corof, result_futures):
        @functools.wraps(corof)
        def wrapper(obj, *args, **kwargs):
            coro = corof(obj._ref, *args, **kwargs)
            return self.run_coroutine(coro, wait=result_futures)
        return wrapper

    def _create_proxy_for(self, klass, resolve_futures=False):
        class Proxy(BaseProxy):
            pass
        for name in dir(klass):
            if name.startswith('_'):
                continue
            member = getattr(klass, name)
            if inspect.iscoroutinefunction(member):
                member = self._create_coroutine_threadsafe(member,
                                                           resolve_futures)
            setattr(Proxy, name, member)
        return Proxy

    def proxy(self, obj, resolve_futures=False):
        if not self.is_alive():
            self.start()
        klass = type(obj)
        key = klass, resolve_futures
        Proxy = self.proxies.get(key)
        if not Proxy:
            Proxy = self._create_proxy_for(klass, resolve_futures)
            self.proxies[key] = Proxy
        return Proxy(obj)

    def tcp(self, host, port, eol=b'\n', resolve_futures=False):
        return self.proxy(TCP(host, port, eol), resolve_futures)


DefaultSynchronousEventLoop = SynchronousEventLoop()
proxy = DefaultSynchronousEventLoop.proxy
tcp = DefaultSynchronousEventLoop.tcp


def aio_loop(queue):
    async def loop():
        ev_loop = asyncio.get_event_loop()
        queue.put(ev_loop)
    asyncio.run(loop())


def aio_in_different_thread():
    import threading, queue
    channel = queue.Queue()
    aio_thread = threading.Thread(target=aio_loop, args=(channel,))
    aio_thread.daemon = True
    aio_thread.start()
    aio_thread.loop = channel.get()
    tcp = TCP('localhost', 12345)
    print(aio_thread.loop)
    print(asyncio.get_event_loop())
    fut = asyncio.run_coroutine_threadsafe(tcp.write_readline(b'*idn?\n'), aio_thread.loop)
    print(fut.result())

if __name__ == '__main__':
    aio_in_different_thread()
    #asyncio.run(main())

