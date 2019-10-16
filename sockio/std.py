import io
import socket
import logging
import functools
import selectors
import threading


class StopEngine(Exception):
    pass


def ensure_connected(f):
    @functools.wraps(f)
    def wrapper(self, *args, **kwargs):
        if self.closed:
            self._open()
        return f(self, *args, **kwargs)
    return wrapper


class RawTCP:

    def __init__(self, host, port):
        self._addr = host, port
        self._sock = socket.create_connection(self._addr)
        self._sock.setblocking(False)
        self._buffer = b''
        self._read_event = threading.Event()
        self._lock = threading.Lock()
        self.closed = False

    def raw_read(self):
        # should only be called when we know an event as occurred
        # because the socket is in non blocking mode
        return self._sock.recv(io.DEFAULT_BUFFER_SIZE)

    def new_data_ready(self, data):
        with self._lock:
            if not data:
                self.closed = True
            else:
                self._buffer += data
            self._read_event.set()

    def close(self):
        self._sock.close()
        self.closed = True
        self._read_event.set()

    def fileno(self):
        return self._sock.fileno()

    def _waituntil(self, c):
        while True:
            pos = self._buffer.find(c)
            if pos != -1:
                return pos + len(c)
            self._read_event.wait()
            self._read_event.clear()
            if self.closed:
                raise ConnectionError('lost connection while waiting for data')

    def _waitexactly(self, n):
        while True:
            size = len(self._buffer)
            if n <= size:
                return
            self._read_event.wait()
            self._read_event.clear()
            if self.closed:
                raise ConnectionError('lost connection while waiting for data')

    def read(self, n):
        with self._lock:
            reply = self._buffer[:n]
            self._buffer = self._buffer[n:]
        return reply

    def readuntil(self, separator=b'\n'):
        n = self._waituntil(separator)
        return self.read(n)

    def readexactly(self, n):
        self._waitexactly(n)
        return self.read(n)

    def write(self, data):
        self._sock.sendall(data)


class TCP:

    def __init__(self, engine, host, port, newline=b'\n'):
        self._log = logging.getLogger(f'TCP({host}:{port})')
        self._engine = engine
        self._sock = None
        self._lock = threading.Lock()
        self.host = host
        self.port = port
        self.newline = newline
        self.closed = True

    def _on_new_data(self, sock, mask):
        assert sock == self
        data = self._sock.raw_read()
        if data:
            self._log.debug(f'recv %r', data)
        else:
            self._log.debug('disconnected')
            self._close()
        self._sock.new_data_ready(data)

    def _open(self):
        if not self.closed:
            raise Exception('must close socket before opening')
        self._sock = RawTCP(self.host, self.port)
        self.closed = False
        self._engine.register(self, self._on_new_data)

    def _close(self):
        if self._sock is not None:
            self._sock.close()
            self._engine.unregister(self)
        self.closed = True

    def open(self):
        with self._lock:
            self._open()

    def close(self):
        with self._lock:
            self._close()

    def _write(self, data):
        self._sock.write(data)
        self._log.debug(f'sendall %r', data)

    def _readline(self):
        return self._sock.readuntil(self.newline)

    def _readlines(self, n):
        for i in range(n):
            yield self._readline()

    @ensure_connected
    def fileno(self):
        return self._sock.fileno()

    @ensure_connected
    def write(self, data):
        with self._lock:
            self._write(data)

    @ensure_connected
    def readline(self):
        with self._lock:
            return self._readline()

    @ensure_connected
    def write_readline(self, data):
        with self._lock:
            self._write(data)
            return self._readline()

    @ensure_connected
    def readlines(self, n):
        with self._lock:
            for i in range(n):
                yield self._readline()

    @ensure_connected
    def write_readlines(self, data, nb_lines):
        with self._lock:
            self._write(data)
            for line in self._readlines():
                yield line


class Engine:

    def __init__(self):
        self._sel = selectors.DefaultSelector()
        self._reader, self._writer = socket.socketpair()
        self._reader.setblocking(False)
        self._reader_stream = self._reader.makefile('rb', 0)
        self._sel.register(self._reader, selectors.EVENT_READ, self._on_action)
        self._started = threading.Event()

    @property
    def running(self):
        return self._started.is_set()

    def start(self):
        if self.running:
            raise RuntimeError('Engine already started')
        task = threading.Thread(target=self.run, name='sockio.EngineTH')
        task.daemon = True
        task.start()
        self._started.wait()

    def stop(self):
        if self.running:
            self._writer.sendall(b'stop\n')

    def run(self):
        self._started.set()
        while True:
            events = self._sel.select()
            for event, event_type in events:
                try:
                    event.data(event.fileobj, event_type)
                except StopEngine:
                    self._started.clear()
                    return
                except:
                    logging.exception('Error handling event:')

    def register(self, conn, cb, mask=selectors.EVENT_READ):
        self._sel.register(conn, mask, cb)

    def unregister(self, conn):
        self._sel.unregister(conn)

    def _on_action(self, sock, event_type):
        assert event_type == selectors.EVENT_READ
        assert sock == self._reader
        command = self._reader_stream.readline()
        if command == b'stop\n':
            raise StopEngine()
        else:
            raise Exception('Unknown command {}'.format(command))

    def tcp(self, host, port, newline=b'\n'):
        if not self.running:
            self.start()
        return TCP(self, host, port, newline=newline)

    def channel(self, url):
        if url.startswith('tcp://'):
            host, port = url[6:].split(':', 1)
            return self.tcp(host, int(port))
        raise ValueError('Unknown connection type')


_default_engine = Engine()

tcp = _default_engine.tcp
channel = _default_engine.channel


if __name__ == '__main__':
    logging.basicConfig(level='INFO')
    engine = Engine()
    engine.start()
    sock = engine.tcp('localhost', 12345)
    sock._log.setLevel(logging.DEBUG)
    sock.write(b'*IDN?\n')
    print(sock.readline())
    print(sock.write_readline(b'*IDN?\n'))


