import pytest

from sockio.py2 import TCP

from conftest import IDN_REQ, IDN_REP, WRONG_REQ, WRONG_REP


def test_socket_creation():
    sock = TCP("example.com", 34567)
    assert sock.host == "example.com"
    assert sock.port == 34567
    assert not sock.connected
    assert sock.connection_counter == 0


def test_open_fail(unused_tcp_port):
    sock = TCP("0", unused_tcp_port)
    assert not sock.connected
    assert sock.connection_counter == 0

    with pytest.raises(ConnectionRefusedError):
        sock.open()
    assert not sock.connected
    assert sock.connection_counter == 0


def test_write_fail(unused_tcp_port):
    sock = TCP("0", unused_tcp_port)
    assert not sock.connected
    assert sock.connection_counter == 0

    with pytest.raises(ConnectionRefusedError):
        sock.write(IDN_REQ)
    assert not sock.connected
    assert sock.connection_counter == 0


def test_write_readline_fail(unused_tcp_port):
    sock = TCP("0", unused_tcp_port)
    assert not sock.connected
    assert sock.connection_counter == 0

    with pytest.raises(ConnectionRefusedError):
        sock.write_readline(IDN_REQ)
    assert not sock.connected
    assert sock.connection_counter == 0


def test_open_close(sio_server, py2_tcp):
    assert not py2_tcp.connected
    assert py2_tcp.connection_counter == 0
    assert sio_server.sockets[0].getsockname() == (py2_tcp.host, py2_tcp.port)

    py2_tcp.open()
    assert py2_tcp.connected
    assert py2_tcp.connection_counter == 1

    with pytest.raises(ConnectionError):
        py2_tcp.open()
    assert py2_tcp.connected
    assert py2_tcp.connection_counter == 1

    py2_tcp.close()
    assert not py2_tcp.connected
    assert py2_tcp.connection_counter == 1
    py2_tcp.open()
    assert py2_tcp.connected
    assert py2_tcp.connection_counter == 2
    py2_tcp.close()
    py2_tcp.close()
    assert not py2_tcp.connected
    assert py2_tcp.connection_counter == 2


def test_write_readline(py2_tcp):
    for request, expected in [(IDN_REQ, IDN_REP), (WRONG_REQ, WRONG_REP)]:
        reply = py2_tcp.write_readline(request)
        assert py2_tcp.connected
        assert py2_tcp.connection_counter == 1
        assert expected == reply


def test_write_readlines(py2_tcp):
    for request, expected in [
        (IDN_REQ, [IDN_REP]),
        (2 * IDN_REQ, 2 * [IDN_REP]),
        (IDN_REQ + WRONG_REQ, [IDN_REP, WRONG_REP]),
    ]:
        gen = py2_tcp.write_readlines(request, len(expected))
        reply = [line for line in gen]
        assert py2_tcp.connected
        assert py2_tcp.connection_counter == 1
        assert expected == reply


def test_writelines_readlines(py2_tcp):
    for request, expected in [
        ([IDN_REQ], [IDN_REP]),
        (2 * [IDN_REQ], 2 * [IDN_REP]),
        ([IDN_REQ, WRONG_REQ], [IDN_REP, WRONG_REP]),
    ]:
        gen = py2_tcp.writelines_readlines(request)
        reply = [line for line in gen]
        assert py2_tcp.connected
        assert py2_tcp.connection_counter == 1
        assert expected == reply


def test_writelines(py2_tcp):
    for request, expected in [
        ([IDN_REQ], [IDN_REP]),
        (2 * [IDN_REQ], 2 * [IDN_REP]),
        ([IDN_REQ, WRONG_REQ], [IDN_REP, WRONG_REP]),
    ]:
        answer = py2_tcp.writelines(request)
        assert py2_tcp.connected
        assert py2_tcp.connection_counter == 1
        assert answer is None

        gen = py2_tcp.readlines(len(expected))
        reply = [line for line in gen]
        assert py2_tcp.connected
        assert py2_tcp.connection_counter == 1
        assert expected == reply


def test_readline(py2_tcp):
    for request, expected in [(IDN_REQ, IDN_REP), (WRONG_REQ, WRONG_REP)]:
        answer = py2_tcp.write(request)
        assert py2_tcp.connected
        assert py2_tcp.connection_counter == 1
        reply = py2_tcp.readline()
        assert expected == reply


def test_readlines(py2_tcp):
    for request, expected in [
        (IDN_REQ, [IDN_REP]),
        (2 * IDN_REQ, 2 * [IDN_REP]),
        (IDN_REQ + WRONG_REQ, [IDN_REP, WRONG_REP]),
    ]:
        answer = py2_tcp.write(request)
        assert py2_tcp.connected
        assert py2_tcp.connection_counter == 1
        gen = py2_tcp.readlines(len(expected))
        reply = [line for line in gen]
        assert expected == reply


def test_read(py2_tcp):
    for request, expected in [(IDN_REQ, IDN_REP), (WRONG_REQ, WRONG_REP)]:
        answer = py2_tcp.write(request)
        assert py2_tcp.connected
        assert py2_tcp.connection_counter == 1
        reply, n = b"", 0
        while len(reply) < len(expected) and n < 2:
            reply += py2_tcp.read(1024)
            n += 1
        assert expected == reply
