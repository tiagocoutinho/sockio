import io


class Lock:
    __slots__ = []
    def _f(*args, **kwargs):
        pass
    acquire = release = __enter__ = __exit__ = _f

_lock = Lock()


def raw_write_readline(stream, data):
    stream.write(data)
    stream.flush()
    return stream.readline()


def write_readline(stream, data, lock=None):
    lock = lock or _lock
    with lock:
        return raw_write_readline(stream, data)


def raw_write_readlines(stream, data, nb_lines):
    stream.write(data)
    for n in range(nb_lines):
        yield stream.readline()


def write_readlines(stream, data, nb_lines, lock=None):
    lock = lock or _lock
    with lock:
        for line in raw_write_readlines(stream, data, nb_lines):
            yield line


def raw_writelines_readlines(stream, lines, nb_lines=None):
    if nb_lines is None:
        nb_lines = len(lines)
    stream.writelines(lines)
    for n in range(nb_lines):
        yield stream.readline()


def writelines_readlines(stream, lines, nb_lines=None, lock=None):
    lock = lock or _lock
    with lock:
        for line in raw_writelines_readlines(stream, data, nb_lines):
            yield line



def RequestReply(sock, mode='rwb', buffering=0, encoding=None, errors=None,
           newline=None, lock=None):
    stream = sock.makefile(mode=mode, buffering=buffering, encoding=encoding,
                           errors=errors, newline=newline)

    stream.write_readline = write_readline.__get__(stream)
    stream.write_readlines = write_readlines.__get__(stream)
    stream.writelines_readlines = writelines_readlines.__get__(stream)
    return stream


"""
sock = socket.create_connection(('www.example.com', 8000))
req_rep = sockio.RequestReply(sock)
req_rep.write_readline(b'*IDN?\n')
"""

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
            self.open()
        return f(self, *args, **kwargs)
    return wrapper


class RawSocket:

    def __init__(self, host, port, newline=b'\n'):
        self._addr = host, port
        self._sock = None
        self._buffer = None
        self._read_event = None
        self.newline = newline

    def raw_read(self):
        data = self._sock.recv(io.DEFAULT_BUFFER_SIZE)
        self._log.debug(f'recv %r', data)
        return data

    def new_data_ready(self, data):
        self._buffer += data
        self._read_event.set()

    def open(self):
        self._sock = socket.create_connection(self._addr)
        self._buffer = b''
        self._read_event = threading.Event()

    def close(self):
        if self._sock is not None:
            self._sock.close()
        self._sock = None
        self._buffer = None
        self._read_event = None

    def fileno(self):
        return self._sock.fileno()

    def wait_newline(self):
        while True:
            pos = self._buffer.find(self.newline)
            if pos != -1:
                return pos + len(self.newline)
            self._read_event.wait()
            self._read_event.clear()

    def consume(self, n):
        reply = self._buffer[:n]
        self._buffer = self._buffer[n:]

    def consume_line(self):
        reply, sep, self._buffer = self._buffer.partition(self.newline)
        return reply + sep

    def write(self, data):
        self._sock.sendall(data)
        self._log.debug(f'sendall %r', data)


class Socket:

    def __init__(self, engine, host, port, newline=b'\n'):
        self._addr = host, port
        self._sock = None
        self._buffer = None
        self._read_event = None
        self._lock = threading.Lock()
        self._log = logging.getLogger(f'Socket({host}:{port})')
        self._engine = engine
        self.closed = True
        self.newline = newline


    def _on_new_data(self, sock, mask):
        assert sock == self
        data = self._sock.recv(io.DEFAULT_BUFFER_SIZE)
        self._log.debug(f'recv %r', data)
        if not data:
            self.close()
            return
        with self._lock:
            self._buffer += data
            self._read_event.set()

    def open(self):
        if not self.closed:
            raise Exception('must close socket before opening')
        with self._lock:
            self._sock = socket.create_connection(self._addr)
            self._buffer = b''
            self._read_event = threading.Event()
            self.closed = False
            self._engine.register(self, self._on_new_data)

    def close(self):
        with self._lock:
            if self._sock is not None:
                self._engine.unregister(self._sock)
                self._sock.close()
            self._sock = None
            self._buffer = None
            self._read_event = None
            self.closed = True

    @ensure_connected
    def fileno(self):
        return self._sock.fileno()

    @ensure_connected
    def readline(self):
        newline = self.newline
        newline_size = len(newline)
        while True:
            pos = self._buffer.find(newline)
            if pos != -1:
                break
            self._read_event.wait()
            self._read_event.clear()
        with self._lock:
            reply = self._buffer[:pos + newline_size]
            self._buffer = self._buffer[pos + newline_size:]
        return reply

    @ensure_connected
    def readlines(self, hint=-1):
        return self._stream.readlines(hint)

    @ensure_connected
    def write(self, data):
        self._sock.sendall(data)
        self._log.debug(f'sendall %r', data)

    @ensure_connected
    def writelines(self, lines):
        return self._stream.writelines(lines)

    @ensure_connected
    def write_readline(self, data):
        self._stream.write(data)
        return self._stream.readline()

    @ensure_connected
    def write_readlines(self, data, nb_lines):
        self._stream.write(data)
        for i in range(nb_lines):
            yield self._stream.readline()

    @ensure_connected
    def writelines_readlines(self, lines, nb_lines=None):
        if nb_lines is None:
            nb_lines = len(lines)
        self._stream.writelines(lines)
        for i in range(nb_lines):
            yield self._stream.readline()


class Engine:

    def __init__(self):
        self.sel = selectors.DefaultSelector()
        self._task = None
        self._reader, self._writer = socket.socketpair()
        self._reader.setblocking(False)
        self._reader_stream = self._reader.makefile('rb', 0)
        self.sel.register(self._reader, selectors.EVENT_READ, self._on_action)

    def start(self):
        self._task = threading.Thread(target=self.run, name='sockio.EngineTH')
        self._task.daemon = True
        self._task.start()

    def run(self):
        while True:
            events = self.sel.select()
            for event, event_type in events:
                try:
                    event.data(event.fileobj, event_type)
                except StopEngine:
                    return
                except:
                    logging.exception('Error handling event:')

    def register(self, conn, cb, mask=selectors.EVENT_READ):
        self.sel.register(conn, mask, cb)

    def unregister(self, conn):
        self.sel.unregister(conn)

    def _on_action(self, sock, event_type):
        assert event_type == selectors.EVENT_READ
        assert sock == self._reader
        command = self._reader_stream.readline()
        if command == b'stop\n':
            raise StopEngine()
        else:
            raise Exception('Unknown command {}'.format(command))

    def socket(self, host, port, newline=b'\n'):
        return Socket(self, host, port, newline=newline)


if __name__ == '__main__':
    logging.basicConfig(level='INFO')
    engine = Engine()
    engine.start()
    sock = engine.socket('localhost', 12345)
    sock._log.setLevel(logging.DEBUG)
    sock.write(b'*IDN?\n')
    print(sock.readline())

"""
engine = Engine()
tcp = engine.TCP('localhost', 8000)
tcp.write_readline(b'*IDN?\n')
"""
