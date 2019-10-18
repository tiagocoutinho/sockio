import asyncio
import logging


from .util import with_log, ensure_connection


log = logging.getLogger('sockio')


class StreamReaderProtocol(asyncio.StreamReaderProtocol):

    def connection_made(self, transport):
        result = super().connection_made(transport)
        self._exec_callback('connection_made_cb', transport)
        return result

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


async def open_connection(host=None, port=None, loop=None, flags=0,
                          on_connection_made=None, on_connection_lost=None,
                          on_eof_received=None):
    if loop is None:
        loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader(loop=loop)
    protocol = StreamReaderProtocol(reader, loop=loop)
    protocol.connection_made_cb = on_connection_made
    protocol.connection_lost_cb = on_connection_lost
    protocol.eof_received_cb = on_eof_received
    transport, _ = await loop.create_connection(
        lambda: protocol, host, port, flags=flags)
    writer = asyncio.StreamWriter(transport, protocol, reader, loop)
    return reader, writer


class Socket:

    def __init__(self, host, port, auto_reconnect=True,
                 on_connection_made=None, on_connection_lost=None,
                 on_eof_received=None):
        self.host = host
        self.port = port
        self.auto_reconnect = auto_reconnect
        self.connection_counter = 0
        self.on_connection_made = on_connection_made
        self.on_connection_lost = on_connection_lost
        self.on_eof_received = on_eof_received
        self.reader = None
        self.writer = None
        self._log = log.getChild('Socket({}:{})'.format(host, port))
        self._lock = asyncio.Lock()

    @with_log
    async def open(self):
        if self.connected:
            raise ConnectionError('socket already open. must close it first')
        self._log.debug('open connection (#%d)', self.connection_counter + 1)
        self.reader, self.writer = await open_connection(
            self.host, self.port,
            on_connection_made=self.on_connection_made,
            on_connection_lost=self.on_connection_lost,
            on_eof_received=self.on_eof_received)
        self.connection_counter += 1

    @with_log
    async def close(self):
        if self.writer is not None:
            self.writer.close()
            await self.writer.wait_closed()
        self.reader = None
        self.writer = None

    @property
    def connected(self):
        if self.reader is None:
            return False
        eof = self.reader.at_eof()
        return not eof

    @with_log
    @ensure_connection
    async def read(self, n=-1):
        return await self.reader.read(n)

    @with_log
    @ensure_connection
    async def readline(self):
        return await self.reader.readline()

    @with_log
    @ensure_connection
    async def readlines(self, n):
        result = []
        for i in range(n):
            result.append(await self.reader.readline())
        return result

    @with_log
    @ensure_connection
    async def readexactly(self, n):
        return await self.reader.readexactly(n)

    @with_log
    @ensure_connection
    async def readuntil(self, separator=b'\n'):
        return await self.reader.readuntil(separator)

    @with_log
    @ensure_connection
    async def write(self, data):
        self.writer.write(data)
        await self.writer.drain()

    @with_log
    @ensure_connection
    async def writelines(self, lines):
        self.writer.writelines(lines)
        await self.writer.drain()

    @with_log
    @ensure_connection
    async def write_readline(self, data):
        self.writer.write(data)
        await self.writer.drain()
        return await self.reader.readline()

    @with_log
    @ensure_connection
    async def write_readlines(self, data, n):
        self.writer.write(data)
        await self.writer.drain()
        result = []
        for i in range(n):
            result.append(await self.reader.readline())
        return result

    @with_log
    @ensure_connection
    async def writelines_readlines(self, lines, n=None):
        if n is None:
            n = len(lines)
        self.writer.writelines(lines)
        await self.writer.drain()
        result = []
        for i in range(n):
            result.append(await self.reader.readline())
        return result


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
    sock = Socket(options.host, options.port)
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
