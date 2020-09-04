import socket
import logging
import functools
import threading

try:
    ConnectionError
except NameError:

    class ConnectionError(socket.error):
        pass

    class ConnectionResetError(socket.error):
        pass


log = logging.getLogger("sockio")


def ensure_closed_on_error(f):
    @functools.wraps(f)
    def wrapper(self, *args, **kwargs):
        try:
            return f(self, *args, **kwargs)
        except socket.error:
            self.close()
            raise

    return wrapper


class Connection(object):
    def __init__(self, host, port, timeout=1.0):
        self.sock = socket.create_connection((host, port))
        self.sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
        self.sock.settimeout(timeout)
        self.fobj = self.sock.makefile("rwb", 0)

    def close(self):
        if self.sock is not None:
            self.sock.close()
        self.sock = None
        self.fobj = None

    def connected(self):
        return self.sock is not None

    is_open = property(connected)

    @ensure_closed_on_error
    def readline(self):
        data = self.fobj.readline()
        if not data:
            raise ConnectionResetError("remote end disconnected")
        return data

    @ensure_closed_on_error
    def read(self, n=-1):
        data = self.fobj.read(n)
        if not data:
            raise ConnectionResetError("remote end disconnected")
        return data

    @ensure_closed_on_error
    def write(self, data):
        return self.fobj.write(data)

    @ensure_closed_on_error
    def writelines(self, lines):
        return self.fobj.writelines(lines)


def ensure_connected(f):
    @functools.wraps(f)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            if not self.connected():
                self._open()
                return f(self, *args, **kwargs)
            else:
                try:
                    return f(self, *args, **kwargs)
                except socket.error:
                    self._open()
                    return f(self, *args, **kwargs)

    return wrapper


class TCP(object):
    def __init__(self, host, port, timeout=1.0):
        self.host = host
        self.port = port
        self.conn = None
        self.timeout = timeout
        self._log = log.getChild("TCP({0}:{1})".format(host, port))
        self._lock = threading.Lock()
        self.connection_counter = 0

    def _open(self):
        if self.connected():
            raise ConnectionError("socket already open")
        self._log.debug("openning connection (#%d)...", self.connection_counter + 1)
        self.conn = Connection(self.host, self.port, timeout=self.timeout)
        self.connection_counter += 1

    def open(self):
        with self._lock:
            self._open()

    def close(self):
        with self._lock:
            if self.conn is not None:
                self.conn.close()
            self.conn = None

    def connected(self):
        return self.conn is not None and self.conn.connected()

    is_open = property(connected)

    @ensure_connected
    def write(self, data):
        return self.conn.write(data)

    @ensure_connected
    def read(self, n=-1):
        return self.conn.read(n)

    @ensure_connected
    def readline(self):
        return self.conn.readline()

    @ensure_connected
    def readlines(self, n):
        return [self.conn.readline() for _ in range(n)]

    @ensure_connected
    def writelines(self, lines):
        return self.conn.writelines(lines)

    @ensure_connected
    def write_readline(self, data):
        self.conn.write(data)
        return self.conn.readline()

    @ensure_connected
    def write_readlines(self, data, n):
        self.conn.write(data)
        return [self.conn.readline() for _ in range(n)]

    @ensure_connected
    def writelines_readlines(self, lines, n=None):
        if n is None:
            n = len(lines)
        self.conn.writelines(lines)
        return [self.conn.readline() for _ in range(n)]


def main(args=None):
    import argparse

    parser = argparse.ArgumentParser()
    log_level_choices = ["critical", "error", "warning", "info", "debug"]
    log_level_choices += [i.upper() for i in log_level_choices]
    parser.add_argument("--host", default="0", help="host / IP")
    parser.add_argument("-p", "--port", type=int, help="port")
    parser.add_argument("--log-level", choices=log_level_choices, default="warning")
    options = parser.parse_args(args)
    fmt = "%(asctime)-15s %(levelname)-5s %(threadName)s %(name)s: %(message)s"
    logging.basicConfig(level=options.log_level.upper(), format=fmt)
    return TCP(options.host, options.port)


if __name__ == "__main__":
    conn = main()
