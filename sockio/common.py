import logging


IPTOS_NORMAL = 0x0
IPTOS_LOWDELAY = 0x10
IPTOS_THROUGHPUT = 0x08
IPTOS_RELIABILITY = 0x04
IPTOS_MINCOST = 0x02
DEFAULT_LIMIT = 2 ** 20  # 1MB


log = logging.getLogger("sockio")


class ConnectionEOFError(ConnectionError):
    pass


class ConnectionTimeoutError(ConnectionError):
    pass
