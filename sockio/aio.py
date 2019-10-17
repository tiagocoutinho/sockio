import asyncio
import logging

from .util import log, ensure_connection


class Socket:

    def __init__(self, host, port, auto_reconnect=True):
        self.host = host
        self.port = port
        self.auto_reconnect = auto_reconnect
        self.connection_counter = 0
        self._reader = None
        self._writer = None
        self._log = logging.getLogger('sockio.Socket({}:{})'.format(host, port))
        self._lock = asyncio.Lock()

    @log
    async def open(self):
        if self.connected:
            raise ConnectionError('socket already open. must close it first')
        self._log.debug('open connection (#%d)', self.connection_counter + 1)
        self._reader, self._writer = await asyncio.open_connection(
            self.host, self.port)
        self.connection_counter += 1

    @log
    async def close(self):
        if self._writer is not None:
            self._writer.close()
            await self._writer.wait_closed()
        self._reader = None
        self._writer = None

    @property
    def connected(self):
        if self._reader is None:
            return False
        eof = self._reader.at_eof()
        return not eof

    @log
    @ensure_connection
    async def read(self, n=-1):
        return await self._reader.read(n)

    @log
    @ensure_connection
    async def readline(self):
        return await self._reader.readline()

    @log
    @ensure_connection
    async def readlines(self, n):
        result = []
        async for i in range(n):
            result.append(await self._reader.readline())
        return result

    @log
    @ensure_connection
    async def readexactly(self, n):
        return await self._reader.readexactly(n)

    @log
    @ensure_connection
    async def readuntil(self, separator=b'\n'):
        return await self._reader.readuntil(separator)

    @log
    @ensure_connection
    async def write(self, data):
        self._writer.write(data)
        await self._writer.drain()

    @log
    @ensure_connection
    async def writelines(self, lines):
        self._writer.writelines(lines)
        await self._writer.drain()

    @log
    @ensure_connection
    async def write_readline(self, data):
        self._writer.write(data)
        await self._writer.drain()
        return await self._reader.readline()

    @log
    @ensure_connection
    async def write_readlines(self, data, n):
        self._writer.write(data)
        await self._writer.drain()
        result = []
        async for i in range(n):
            result.append(await self._reader.readline())
        return result

    @log
    @ensure_connection
    async def writelines_readlines(self, lines, n=None):
        if n is None:
            n = len(lines)
        self._writer.writelines(lines)
        await self._writer.drain()
        result = []
        async for i in range(n):
            result.append(await self._reader.readline())
        return result


def app(options):
    async def run():
        sock = Socket(options.host, options.port)
        request = options.request
        lines = request.count('\n')
        async for r in sock.write_readlines(request.encode(), lines):
            print(r)
    asyncio.run(run(), debug=options.debug)


def main(cb, args=None):
    import argparse
    parser = argparse.ArgumentParser()
    log_level_choices = ["critical", "error", "warning", "info", "debug"]
    log_level_choices += [i.upper() for i in log_level_choices]
    parser.add_argument('--host', default='0',
                        help='SCPI device host name / IP')
    parser.add_argument('-p', '--port', type=int, help='SCPI device port')
    parser.add_argument('-r', '--request', default='*IDN?\n',
                        help='SCPI request [%(default)s]')
    parser.add_argument("--log-level", choices=log_level_choices, default="warning")
    parser.add_argument('-d', '--debug', action='store_true')
    options = parser.parse_args(args)
    if not options.request.endswith('\n'):
        options.request += '\n'
    fmt = '%(asctime)-15s %(levelname)-5s %(threadName)s %(name)s: %(message)s'
    logging.basicConfig(level=options.log_level.upper(), format=fmt)
    cb(options)


if __name__ == '__main__':
    main(app)
