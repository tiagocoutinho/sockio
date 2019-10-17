import asyncio
import inspect
import functools
import threading

from . import aio


class BaseProxy:

    def __init__(self, ref):
        self._ref = ref

    def __getattr__(self, name):
        return getattr(self._ref, name)


def ensure_running(f):
    @functools.wraps(f)
    def wrapper(self, *args, **kwargs):
        if not self.is_alive():
            self.start()
        return f(self, *args, **kwargs)
    return wrapper


class EventLoop(threading.Thread):

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

    @ensure_running
    def call_soon(self, func, *args, **kwargs):
        f = functools.partial(func, *args, **kwargs)
        return self.loop.call_soon_threadsafe(f)

    @ensure_running
    def run_coroutine(self, coro):
         return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def _create_coroutine_threadsafe(self, corof, resolve_future):
        @functools.wraps(corof)
        def wrapper(obj, *args, **kwargs):
            coro = corof(obj._ref, *args, **kwargs)
            future = self.run_coroutine(coro)
            return future.result() if resolve_future else future
        return wrapper

    def _create_asyncgenerator_threadsafe(self, async_genf, resolve_future):
        async def corof(*args, **kwargs):
            return [i async for i in async_genf(*args, **kwargs)]
        return self._create_coroutine_threadsafe(corof, resolve_future)

    def _create_proxy_for(self, klass, resolve_futures=True):
        class Proxy(BaseProxy):
            pass
        for name in dir(klass):
            if name.startswith('_'):
                continue
            member = getattr(klass, name)
            if asyncio.iscoroutinefunction(member):
                member = self._create_coroutine_threadsafe(
                    member, resolve_futures)
            elif inspect.isasyncgenfunction(member):
                member = self._create_asyncgenerator_threadsafe(
                    member, resolve_futures)
            setattr(Proxy, name, member)
        return Proxy

    @ensure_running
    def proxy(self, obj, resolve_futures=True):
        klass = type(obj)
        key = klass, resolve_futures
        Proxy = self.proxies.get(key)
        if not Proxy:
            Proxy = self._create_proxy_for(klass, resolve_futures)
            self.proxies[key] = Proxy
        return Proxy(obj)

    @ensure_running
    def socket(self, host, port, auto_reconnect=True,
               resolve_futures=True):
        sock = aio.Socket(host, port, auto_reconnect=auto_reconnect)
        return self.proxy(sock, resolve_futures)


DefaultEventLoop = EventLoop()
Socket = DefaultEventLoop.socket


def app(options):
    sock = Socket(options.host, options.port)
    print(sock.write_readline(options.request.encode()))


if __name__ == '__main__':
    from .aio import main
    main(app)
