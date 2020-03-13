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


log = logging.getLogger('sockio')


def ensure_connection(f):
    assert asyncio.iscoroutinefunction(f)
    @functools.wraps(f)
    async def wrapper(self, *args, **kwargs):
        if self.auto_reconnect and not self.connected:
            await self.open()
        return await f(self, *args, **kwargs)
    return wrapper


class StreamReaderProtocol(asyncio.StreamReaderProtocol):

    def connection_lost(self, exc):
        result = super().connection_lost(exc)
        self._exec_callback('connection_lost_cb', exc)
        return result

    def eof_received(self):
        result = super().eof_received()
        self._exec_callback('eof_received_cb')
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
            log.exception(
                'Error in %s callback %r', name, callback.__name__)


class StreamReader(asyncio.StreamReader):

    async def readline(self, eol=b'\n'):
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
                del self._buffer[:e.consumed + len(eol)]
            else:
                self._buffer.clear()
            self._maybe_resume_transport()
            raise ValueError(e.args[0])
        return line


async def open_connection(host=None, port=None, loop=None,
                          limit=DEFAULT_LIMIT, flags=0,
                          on_connection_lost=None,
                          on_eof_received=None,
                          no_delay=True,
                          tos=IPTOS_LOWDELAY):
    if loop is None:
        loop = asyncio.get_event_loop()
    reader = StreamReader(limit=limit, loop=loop)
    protocol = StreamReaderProtocol(reader, loop=loop)
    protocol.connection_lost_cb = on_connection_lost
    protocol.eof_received_cb = on_eof_received
    transport, _ = await loop.create_connection(
        lambda: protocol, host, port, flags=flags)
    writer = asyncio.StreamWriter(transport, protocol, reader, loop)
    sock = writer.transport.get_extra_info('socket')
    if hasattr(socket, 'TCP_NODELAY'):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1 if no_delay else 0)
    if hasattr(socket, 'IP_TOS'):
        sock.setsockopt(socket.SOL_IP, socket.IP_TOS, tos)
    return reader, writer


class TCP:

    def __init__(self, host, port, eol=b'\n', auto_reconnect=True,
                 on_connection_made=None, on_connection_lost=None,
                 on_eof_received=None, buffer_size=DEFAULT_LIMIT,
                 no_delay=True, tos=IPTOS_LOWDELAY):
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
        self.reader = None
        self.writer = None
        self._log = log.getChild('TCP({}:{})'.format(host, port))

    def __aiter__(self):
        return self

    @ensure_connection
    async def __anext__(self):
        val = await self.reader.readline()
        if val == b'':
            raise StopAsyncIteration
        return val

    async def open(self):
        if self.connected:
            raise ConnectionError('socket already open')
        self._log.debug('open connection (#%d)', self.connection_counter + 1)
        self.reader, self.writer = await open_connection(
            self.host, self.port, limit=self.buffer_size,
            on_connection_lost=self.on_connection_lost,
            on_eof_received=self.on_eof_received,
            no_delay=self.no_delay, tos=self.tos)
        if self.on_connection_made is not None:
            try:
                res = self.on_connection_made()
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                log.exception(
                    'Error in connection_made callback %r',
                    self.on_connection_made.__name__)
        self.connection_counter += 1

    async def close(self):
        if self.writer is not None:
            self.writer.close()
            if PY_37:
                await self.writer.wait_closed()
        self.reader = None
        self.writer = None

    @property
    def connected(self):
        if self.reader is None:
            return False
        eof = self.reader.at_eof()
        return not eof

    async def _read(self, n=-1):
        return await self.reader.read(n)

    async def _readline(self, eol=None):
        if eol is None:
            eol = self.eol
        return await self.reader.readline(eol=eol)

    async def _readlines(self, n, eol=None):
        if eol is None:
            eol = self.eol
        result = []
        for _ in range(n):
            result.append(await self.reader.readline(eol=eol))
        return result

    async def _write(self, data):
        self.writer.write(data)
        await self.writer.drain()

    async def _writelines(self, lines):
        self.writer.writelines(lines)
        await self.writer.drain()

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
        return await self.reader.readexactly(n)

    @ensure_connection
    async def readuntil(self, separator=b'\n'):
        return await self.reader.readuntil(separator)

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


def parse_args(args=None):
    import argparse
    parser = argparse.ArgumentParser()
    log_level_choices = ["critical", "error", "warning", "info", "debug"]
    log_level_choices += [i.upper() for i in log_level_choices]
    parser.add_argument('--host', default='0',
                        help='SCPI device host name / IP')
    parser.add_argument('-p', '--port', type=int, help='SCPI device port')
    parser.add_argument('-r', '--request', default='*IDN?\n',
                        help='SCPI request [%(default)s]')
    parser.add_argument("--log-level", choices=log_level_choices,
                        default="warning")
    parser.add_argument('-d', '--debug', action='store_true')
    options = parser.parse_args(args)
    if not options.request.endswith('\n'):
        options.request += '\n'
    fmt = '%(asctime)-15s %(levelname)-5s %(threadName)s %(name)s: %(message)s'
    logging.basicConfig(level=options.log_level.upper(), format=fmt)
    return options


async def run(options):
    sock = TCP(options.host, options.port)
    request = options.request
    nb_lines = request.count('\n')
    lines = await sock.write_readlines(request.encode(), nb_lines)
    for line in lines:
        print(line)


def main(args=None):
    options = parse_args(args=args)
    return run(options)


if __name__ == '__main__':
    asyncio.run(main())
