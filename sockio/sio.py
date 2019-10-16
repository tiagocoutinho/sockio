import threading

from .aio import Socket


class BaseProxy:

    def __init__(self, ref):
        self._ref = ref


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
                member = self._create_coroutine_threadsafe(
                    member, resolve_futures)
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

    def socket(self, host, port, eol=b'\n', resolve_futures=False):
        return self.proxy(Socket(host, port, eol), resolve_futures)


DefaultEventLoop = EventLoop()
Socket = DefaultEventLoop.socket


