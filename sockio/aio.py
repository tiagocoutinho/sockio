import sys
import socket
import asyncio
import logging
import functools


PY_37 = sys.version_info >= (3, 7)

IPTOS_NORMAL = 0x0
IPTOS_LOWDELAY = 0x10
IPTOS_THROUGHPUT = 0x08
IPTOS_RELIABILITY = 0x04
IPTOS_MINCOST = 0x02
DEFAULT_LIMIT = 2 ** 20  # 1Mb


log = logging.getLogger("sockio")


class ConnectionEOFError(ConnectionError):
    pass


class ConnectionTimeoutError(ConnectionError):
    pass


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
        except asyncio.TimeoutError:
            addr = str((self.host, self.port))
            raise ConnectionTimeoutError("{} call timeout on {}".format(name, addr))

    return wrapper


def raw_handle_read(f):
    assert asyncio.iscoroutinefunction(f)

    @functools.wraps(f)
    async def wrapper(self, *args, **kwargs):
        try:
            reply = await f(self, *args, **kwargs)
        except ConnectionError:
            await self.close()
            raise
        if not reply:
            await self.close()
            raise ConnectionEOFError("Connection closed by peer")
        return reply

    return wrapper


class StreamReaderProtocol(asyncio.StreamReaderProtocol):
    def connection_lost(self, exc):
        result = super().connection_lost(exc)
        self._exec_callback("connection_lost_cb", exc)
        return result

    def eof_received(self):
        result = super().eof_received()
        self._exec_callback("eof_received_cb")
        return result

    def _exec_callback(self, name, *args, **kwargs):
        callback = getattr(self, name, None)
        if callback is None:
            return
        try:
            res = callback(*args, **kwargs)
            if asyncio.iscoroutine(res):
                self._loop.create_task(res)
        except Exception:
            log.exception("Error in %s callback %r", name, callback.__name__)


class StreamReader(asyncio.StreamReader):
    async def readline(self, eol=b"\n"):
        # This implementation is a copy of the asyncio.StreamReader.readline()
        # with the purpose of supporting different EOL characters.
        # we walk on thin ice here: we rely on the internal _buffer and
        # _maybe_resume_transport members
        try:
            line = await self.readuntil(eol)
        except asyncio.IncompleteReadError as e:
            return e.partial
        except asyncio.LimitOverrunError as e:
            if self._buffer.startswith(eol, e.consumed):
                del self._buffer[: e.consumed + len(eol)]
            else:
                self._buffer.clear()
            self._maybe_resume_transport()
            raise ValueError(e.args[0])
        return line

    def __len__(self):
        return len(self._buffer)

    def reset(self):
        self._buffer.clear()


async def open_connection(
    host=None,
    port=None,
    loop=None,
    limit=DEFAULT_LIMIT,
    flags=0,
    on_connection_lost=None,
    on_eof_received=None,
    no_delay=True,
    tos=IPTOS_LOWDELAY,
):
    if loop is None:
        loop = asyncio.get_event_loop()
    reader = StreamReader(limit=limit, loop=loop)
    protocol = StreamReaderProtocol(reader, loop=loop)
    protocol.connection_lost_cb = on_connection_lost
    protocol.eof_received_cb = on_eof_received
    transport, _ = await loop.create_connection(
        lambda: protocol, host, port, flags=flags
    )
    writer = asyncio.StreamWriter(transport, protocol, reader, loop)
    sock = writer.transport.get_extra_info("socket")
    if hasattr(socket, "TCP_NODELAY") and no_delay:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    if hasattr(socket, "IP_TOS"):
        sock.setsockopt(socket.SOL_IP, socket.IP_TOS, tos)
    return reader, writer


class BaseStream:
    """Base asynchronous iterator stream helper for TCP connections"""

    def __init__(self, tcp):
        self.tcp = tcp

    async def _read(self):
        raise NotImplementedError

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return await self._read()
        except ConnectionEOFError:
            raise StopAsyncIteration


class LineStream(BaseStream):
    """Line based asynchronous iterator stream helper for TCP connections"""

    def __init__(self, tcp, eol=None):
        super().__init__(tcp)
        self.eol = eol

    async def _read(self):
        return await self.tcp.readline(eol=self.eol)


class BlockStream(BaseStream):
    """
    Fixed based asynchronous iterator stream helper for TCP connections.

    - If limit is an int the block is of fixed size
      (TCP.readexactly semantics)
    - If limit is a string, block ends when the limit string is
      found (TCP.readuntil semantics)
    """

    def __init__(self, tcp, limit):
        super().__init__(tcp)
        self.limit = limit

    async def _read(self):
        try:
            if isinstance(self.limit, int):
                return await self.tcp.readexactly(self.limit)
            else:
                return await self.tcp.readuntil(self.limit)
        except asyncio.IncompleteReadError as error:
            if error.partial:
                raise
            else:
                raise ConnectionEOFError()


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
        buffer_size=DEFAULT_LIMIT,
        no_delay=True,
        tos=IPTOS_LOWDELAY,
        connection_timeout=None,
        timeout=None,
    ):
        self.host = host
        self.port = port
        self.eol = eol
        self.buffer_size = buffer_size
        self.auto_reconnect = auto_reconnect
        self.connection_counter = 0
        self.on_connection_made = on_connection_made
        self.on_connection_lost = on_connection_lost
        self.on_eof_received = on_eof_received
        self.no_delay = no_delay
        self.tos = tos
        self.connection_timeout = connection_timeout
        self.timeout = timeout
        self.reader = None
        self.writer = None
        self._log = log.getChild("TCP({}:{})".format(host, port))

    def __del__(self):
        if self.writer is not None:
            loop = self.writer._loop  # !watch out: access internal stream loop
            if loop is not None and not loop.is_closed():
                self.writer.close()
            else:
                self._log.warning("could not close stream: loop closed")

    def __aiter__(self):
        return LineStream(self)

    async def open(self, **kwargs):
        connection_timeout = kwargs.get("timeout", self.connection_timeout)
        if self.connected():
            raise ConnectionError("socket already open")
        self._log.debug("open connection (#%d)", self.connection_counter + 1)
        # make sure everything is clean before creating a new connection
        await self.close()
        coro = open_connection(
            self.host,
            self.port,
            limit=self.buffer_size,
            on_connection_lost=self.on_connection_lost,
            on_eof_received=self.on_eof_received,
            no_delay=self.no_delay,
            tos=self.tos,
        )
        if connection_timeout is not None:
            coro = asyncio.wait_for(coro, connection_timeout)

        try:
            self.reader, self.writer = await coro
        except asyncio.TimeoutError:
            addr = self.host, self.port
            raise ConnectionTimeoutError("Connect call timeout on {}".format(addr))

        if self.on_connection_made is not None:
            try:
                res = self.on_connection_made()
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                log.exception(
                    "Error in connection_made callback %r",
                    self.on_connection_made.__name__,
                )
        self.connection_counter += 1

    async def close(self):
        try:
            if self.writer is not None:
                self.writer.close()
                if PY_37:
                    await self.writer.wait_closed()
        finally:
            self.reader = None
            self.writer = None

    def in_waiting(self):
        return len(self.reader) if self.connected() else 0

    def connected(self):
        return self.reader is not None and not self.at_eof()

    def at_eof(self):
        return self.reader is not None and self.reader.at_eof()

    @raw_handle_read
    async def _read(self, n=-1):
        return await self.reader.read(n)

    @raw_handle_read
    async def _readexactly(self, n):
        return await self.reader.readexactly(n)

    @raw_handle_read
    async def _readuntil(self, separator=b"\n"):
        return await self.reader.readuntil(separator)

    @raw_handle_read
    async def _readline(self, eol=None):
        if eol is None:
            eol = self.eol
        return await self.reader.readline(eol=eol)

    async def _readlines(self, n, eol=None):
        if eol is None:
            eol = self.eol
        replies = []
        for i in range(n):
            reply = await self._readline(eol=eol)
            replies.append(reply)
        return replies

    async def _write(self, data):
        try:
            self.writer.write(data)
            await self.writer.drain()
        except ConnectionError:
            await self.close()
            raise

    async def _writelines(self, lines):
        try:
            self.writer.writelines(lines)
            await self.writer.drain()
        except ConnectionError:
            await self.close()
            raise

    @ensure_connection
    async def read(self, n=-1):
        return await self._read(n)

    @ensure_connection
    async def readline(self, eol=None):
        return await self._readline(eol=eol)

    @ensure_connection
    async def readlines(self, n, eol=None):
        return await self._readlines(n, eol=eol)

    @ensure_connection
    async def readexactly(self, n):
        return await self._readexactly(n)

    @ensure_connection
    async def readuntil(self, separator=b"\n"):
        return await self._readuntil(separator)

    @ensure_connection
    async def readbuffer(self):
        """Read all bytes currently available in the underlying buffer"""
        size = self.in_waiting()
        return (await self._read(size)) if size else b""

    @ensure_connection
    async def write(self, data):
        return await self._write(data)

    @ensure_connection
    async def writelines(self, lines):
        return await self._writelines(lines)

    @ensure_connection
    async def write_readline(self, data, eol=None):
        await self._write(data)
        return await self._readline(eol=eol)

    @ensure_connection
    async def write_readlines(self, data, n, eol=None):
        await self._write(data)
        return await self._readlines(n, eol=eol)

    @ensure_connection
    async def writelines_readlines(self, lines, n=None, eol=None):
        if n is None:
            n = len(lines)
        await self._writelines(lines)
        return await self._readlines(n, eol=eol)

    def reset_input_buffer(self):
        if self.connected():
            self.reader.reset()
