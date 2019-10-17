import asyncio
import inspect
import functools


class log_args:
    __slots__ = 'args',
    def __init__(self, *args):
        self.args = args

    def __repr__(self):
        if not self.args:
            return ''
        args = repr(self.args)
        return args if len(args) < 80 else args[:74] + '[...]\''


def log(f):
    name = f.__name__
    if asyncio.iscoroutinefunction(f):
        @functools.wraps(f)
        async def wrapper(self, *args, **kwargs):
            self._log.debug('[I] %s (%r)', name, log_args(*args))
            result = await f(self, *args, **kwargs)
            if result is None:
                self._log.debug('[O] %s', name)
            else:
                self._log.debug('[O] %s %r', name, log_args(result))
            return result
    elif inspect.isasyncgenfunction(f):
        @functools.wraps(f)
        async def wrapper(self, *args, **kwargs):
            self._log.debug('[I] %s (%r)', name, log_args(*args))
            async for item in f(self, *args, **kwargs):
                self._log.debug('[Y] %s %s', name, log_args(item))
                yield item
    else:
        @functools.wraps(f)
        def wrapper(self, *args, **kwargs):
            self._log.debug('[I] %s(%r)', name, log_args(*args))
            result = f(self, *args, **kwargs)
            self._log.debug('[O] %s %r', name, log_args(result))
            return result
    return wrapper


def ensure_connection(f):
    if asyncio.iscoroutinefunction(f):
        async def wrapper(self, *args, **kwargs):
            async with self._lock:
                if self.auto_reconnect and not self.connected:
                    await self.open()
                return await f(self, *args, **kwargs)
    elif inspect.isasyncgenfunction(f):
        async def wrapper(self, *args, **kwargs):
            async with self._lock:
                if self.auto_reconnect and not self.connected:
                    await self.open()
                async_gen = f(self, *args, **kwargs)
            async for line in async_gen:
                yield line
    return functools.wraps(f)(wrapper)
