import socket
import asyncio
import functools

from async_timeout import timeout

from .common import IPTOS_LOWDELAY, ConnectionEOFError, ConnectionTimeoutError, log


def configure_socket(sock, no_delay=True, tos=IPTOS_LOWDELAY, keep_alive=None):
    if hasattr(socket, "TCP_NODELAY") and no_delay:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    if hasattr(socket, "IP_TOS"):
        sock.setsockopt(socket.SOL_IP, socket.IP_TOS, tos)
    if keep_alive is not None and hasattr(socket, "SO_KEEPALIVE"):
        if isinstance(keep_alive, (int, bool)):
            keep_alive = dict(active=1 if keep_alive in {1, True} else False)
        active = keep_alive.get('active')
        idle = keep_alive.get('idle')  # aka keepalive_time
        interval = keep_alive.get('interval')  # aka keepalive_intvl
        retry = keep_alive.get('retry')  # aka keepalive_probes
        if active is not None:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, active)
        if idle is not None:
            sock.setsockopt(socket.SOL_TCP, socket.TCP_KEEPIDLE, idle)
        if interval is not None:
            sock.setsockopt(socket.SOL_TCP, socket.TCP_KEEPINTVL, interval)
        if retry is not None:
            sock.setsockopt(socket.SOL_TCP, socket.TCP_KEEPCNT, retry)


async def open_connection(
    host=None,
    port=None,
    loop=None,
    no_delay=True,
    tos=IPTOS_LOWDELAY,
    keep_alive=None,
):
    if loop is None:
        loop = asyncio.get_event_loop()
    sock = socket.socket()
    sock.setblocking(False)
    configure_socket(sock, no_delay=no_delay, tos=tos, keep_alive=keep_alive)
    await loop.sock_connect(sock, (host, port))
    return sock


def ensure_connection(f):
    assert asyncio.iscoroutinefunction(f)
    name = f.__name__

    @functools.wraps(f)
    async def wrapper(self, *args, **kwargs):
        if self.auto_reconnect and not self.connected():
            await self.open()
        timeout = kwargs.pop("timeout", self.timeout)
        coro = f(self, *args, **kwargs)
        if timeout is not None:
            coro = asyncio.wait_for(coro, timeout)
        try:
            return await coro
        except asyncio.TimeoutError as error:
            msg = "{} call timeout on '{}:{}'".format(name, self.host, self.port)
            raise ConnectionTimeoutError(msg) from error

    return wrapper


class RawTCP:

    def __init__(
        self,
        host,
        port,
        eol=b"\n",
        no_delay=True,
        tos=IPTOS_LOWDELAY,
        keep_alive=None,
    ):
        self.host = host
        self.port = port
        self.eol = eol
        self.no_delay = no_delay
        self.tos = tos
        self.keep_alive = keep_alive
        self._sock = None
        self._read_buffer = b""
        self._read_error = None
        self._read_task = None
        self._read_event = asyncio.Event()
        self._log = log.getChild("RawTCP({}:{})".format(host, port))

    def __del__(self):
        self.close()

    def __repr__(self):
        return "{}(host={}, port={}, connected={})".format(
            type(self).__name__, self.host, self.port, self.connected()
        )

    async def _read_loop(self):
        loop = asyncio.get_event_loop()
        try:
            while True:
                data = await loop.sock_recv(self._sock, 2**14)
                if not data:  # EOF
                    raise ConnectionEOFError("EOF reached")
                self._log.debug("received %r", data)
                self._read_buffer += data
                self._read_event.set()
        except OSError as error:
            self._log.debug("OSError: %r", error)
            self._read_error = error
            self._read_task = None
            self._read_event.set()
            self.close()

    def _consume(self, size):
        data = self._read_buffer[:size]
        self._read_buffer = self._read_buffer[size:]
        return data

    async def _wait_for_data(self):
        await self._read_event.wait()
        self._read_event.clear()
        if self._read_error is not None:
            raise self._read_error

    async def open(self):
        self._sock = await open_connection(
            self.host,
            self.port,
            no_delay=self.no_delay,
            tos=self.tos,
            keep_alive=self.keep_alive
        )
        self._read_task = asyncio.create_task(self._read_loop())

    def close(self):
        if self._sock:
            self._sock.close()
            self._sock = None

    def connected(self):
        return self._sock is not None and self._read_task is not None

    def in_waiting(self):
        return len(self._read_buffer)

    async def write(self, data):
        loop = asyncio.get_event_loop()
        await loop.sock_sendall(self._sock, data)

    async def readline(self, eol=None):
        if eol is None:
            eol = self.eol
        size = self._read_buffer.find(eol)
        while size == -1:
            await self._wait_for_data()
            size = self._read_buffer.find(eol)
        size += len(eol)
        return self._consume(size)

    async def readexactly(self, size):
        while len(buffer) < size:
            await self._wait_for_data()
        return self._consume(size)


class TCP:

    def __init__(
        self,
        host,
        port,
        eol=b"\n",
        auto_reconnect=True,
        on_connection_made=None,
        on_connection_lost=None,
        on_eof_received=None,
        no_delay=True,
        tos=IPTOS_LOWDELAY,
        connection_timeout=None,
        timeout=None,
        keep_alive=None,
    ):
        self.host = host
        self.port = port
        self.eol = eol
        self.auto_reconnect = auto_reconnect
        self.connection_counter = 0
        self.on_connection_made = on_connection_made
        self.on_connection_lost = on_connection_lost
        self.on_eof_received = on_eof_received
        self.no_delay = no_delay
        self.tos = tos
        self.connection_timeout = connection_timeout
        self.timeout = timeout
        self.keep_alive = keep_alive
        self._sock = None
        self._log = log.getChild("TCP({}:{})".format(host, port))

    def __repr__(self):
        return "{}({}, {})".format(type(self).__name__, self.host, self.port)

    async def _on_connection_made(self):
        if self.on_connection_made is None:
            return
        try:
            res = self.on_connection_made()
            if asyncio.iscoroutine(res):
                await res
        except Exception:
            log.exception(
                "Error in connection_made callback %r",
                self.on_connection_made.__name__,
            )

    def in_waiting(self):
        return 0 if self._sock is None else self._sock.in_waiting()

    def connected(self):
        return self._sock is not None and self._sock.connected()

    def close(self):
        if self._sock:
            self._sock.close()
            self._sock = None

    async def open(self, **kwargs):
        connection_timeout = kwargs.get("timeout", self.connection_timeout)
        if self.connected():
            raise ConnectionError("socket already open")
        self._log.debug("open connection (#%d)", self.connection_counter + 1)
        sock = RawTCP(
            self.host,
            self.port,
            eol=self.eol,
            no_delay=self.no_delay,
            tos=self.tos,
            keep_alive=self.keep_alive,
        )
        coro = sock.open()
        if connection_timeout is not None:
            coro = asyncio.wait_for(coro, connection_timeout)
        try:
            await coro
        except asyncio.TimeoutError:
            addr = self.host, self.port
            raise ConnectionTimeoutError("Connect call timeout on {}".format(addr))
        self._sock = sock
        await self._on_connection_made()
        self.connection_counter += 1

    @ensure_connection
    async def write(self, data):
        return await self._sock.write(data)

    @ensure_connection
    async def readline(self, eol=None):
        return await self._sock.readline(eol=eol)

    @ensure_connection
    async def write_readline(self, data, eol=None):
        await self._sock.write(data)
        return await self._sock.readline(eol=eol)
