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


class Socket:

    def __init__(self, host, port):
        self._addr = host, port
        self._stream = None

    @property
    def closed(self):
        return self._stream is None or self._stream.closed

    def open(self):
        if not self.closed:
            raise Exception('must close socket before opening')
        self._stream = socket.create_connection(self._addr).makefile('rwb', 0)

    @ensure_connected
    def fileno(self):
        return self._stream.fileno()

    @ensure_connected
    def readline(self, size=-1):
        return self._stream.readline(size)

    @ensure_connected
    def readlines(self, hint=-1):
        return self._stream.readlines(hint)

    @ensure_connected
    def write(self, data):
        return self._stream.write(data)

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
        conn.setblocking(False)
        self.sel.register(conn, mask, cb)

    def _on_action(self, sock, event_type):
        assert event_type == selectors.EVENT_READ
        assert sock == self._reader
        command = self._reader_stream.readline()
        if command == b'stop\n':
            raise StopEngine()
        else:
            raise Exception('Unknown command {}'.format(command))


if __name__ == '__main__':
    sock = socket.create_connection(('dctbl04albaem202', 5025))
    def cb(sock, mask):
        print(sock.recv(1024))
    engine = Engine()
    engine.register(sock, cb)
    engine.start()


"""
engine = Engine()
tcp = engine.TCP('localhost', 8000)
tcp.write_readline(b'*IDN?\n')
"""
