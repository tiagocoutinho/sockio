import asyncio
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


def with_log(f):
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
        @functools.wraps(f)
        async def wrapper(self, *args, **kwargs):
            async with self._lock:
                if self.auto_reconnect and not self.connected:
                    await self.open()
                return await f(self, *args, **kwargs)
    else:
        wrapper = f
    return wrapper
