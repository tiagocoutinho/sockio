__version__ = "0.13.0"


CONCURRENCY_MAP = {
    "sync": "sync",
    "syncio": "sync",
    "async": "async",
    "asyncio": "async",
}


def socket_for_url(url, *args, **kwargs):
    conc = kwargs.pop("concurrency", "async")
    concurrency = CONCURRENCY_MAP.get(conc)
    if concurrency == "async":
        from . import aio

        return aio.socket_for_url(url, *args, **kwargs)
    elif concurrency == "sync":
        from . import sio

        return sio.socket_for_url(url, *args, **kwargs)
    raise ValueError("unsupported concurrency {!r}".format(conc))
