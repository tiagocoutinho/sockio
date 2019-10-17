import pytest

from sockio.sio import Socket

from conftest import IDN_REQ, IDN_REP, WRONG_REQ, WRONG_REP


def test_socket_creation():
    sock = Socket('example.com', 34567)
    assert sock.host == 'example.com'
    assert sock.port == 34567
    assert sock.auto_reconnect == True
    assert not sock.connected
    assert sock.connection_counter == 0


def test_open_fail(unused_tcp_port):
    sock = Socket('0', unused_tcp_port)
    assert not sock.connected
    assert sock.connection_counter == 0

    with pytest.raises(ConnectionRefusedError):
        sock.open()
    assert not sock.connected
    assert sock.connection_counter == 0


def test_write_fail(unused_tcp_port):
    sock = Socket('0', unused_tcp_port)
    assert not sock.connected
    assert sock.connection_counter == 0

    with pytest.raises(ConnectionRefusedError):
        sock.write(IDN_REQ)
    assert not sock.connected
    assert sock.connection_counter == 0


def test_write_readline_fail(unused_tcp_port):
    sock = Socket('0', unused_tcp_port)
    assert not sock.connected
    assert sock.connection_counter == 0

    with pytest.raises(ConnectionRefusedError):
        sock.write_readline(IDN_REQ)
    assert not sock.connected
    assert sock.connection_counter == 0


def test_open_close(sio_server, sio_sock):
    assert not sio_sock.connected
    assert sio_sock.connection_counter == 0
    assert sio_server.sockets[0].getsockname() == (sio_sock.host, sio_sock.port)

    sio_sock.open()
    assert sio_sock.connected
    assert sio_sock.connection_counter == 1

    with pytest.raises(ConnectionError):
        sio_sock.open()
    assert sio_sock.connected
    assert sio_sock.connection_counter == 1

    sio_sock.close()
    assert not sio_sock.connected
    assert sio_sock.connection_counter == 1
    sio_sock.open()
    assert sio_sock.connected
    assert sio_sock.connection_counter == 2
    sio_sock.close()
    sio_sock.close()
    assert not sio_sock.connected
    assert sio_sock.connection_counter == 2


def test_write_readline(sio_sock):
    for request, expected in [(IDN_REQ,  IDN_REP),
                              (WRONG_REQ,  WRONG_REP)]:
        reply = sio_sock.write_readline(request)
        assert sio_sock.connected
        assert sio_sock.connection_counter == 1
        assert expected == reply


def test_write_readlines(sio_sock):
    for request, expected in [(IDN_REQ,  [IDN_REP]), (2*IDN_REQ,  2*[IDN_REP]),
                              (IDN_REQ + WRONG_REQ,  [IDN_REP, WRONG_REP])]:
        gen = sio_sock.write_readlines(request, len(expected))
        reply = [line for line in gen]
        assert sio_sock.connected
        assert sio_sock.connection_counter == 1
        assert expected == reply


def test_writelines_readlines(sio_sock):
    for request, expected in [([IDN_REQ],  [IDN_REP]), (2*[IDN_REQ],  2*[IDN_REP]),
                              ([IDN_REQ, WRONG_REQ],  [IDN_REP, WRONG_REP])]:
        gen = sio_sock.writelines_readlines(request)
        reply = [line for line in gen]
        assert sio_sock.connected
        assert sio_sock.connection_counter == 1
        assert expected == reply


def test_writelines(sio_sock):
    for request, expected in [([IDN_REQ],  [IDN_REP]), (2*[IDN_REQ],  2*[IDN_REP]),
                              ([IDN_REQ, WRONG_REQ],  [IDN_REP, WRONG_REP])]:
        answer = sio_sock.writelines(request)
        assert sio_sock.connected
        assert sio_sock.connection_counter == 1
        assert answer is None

        gen = sio_sock.readlines(len(expected))
        reply = [line for line in gen]
        assert sio_sock.connected
        assert sio_sock.connection_counter == 1
        assert expected == reply


def test_readline(sio_sock):
    for request, expected in [(IDN_REQ,  IDN_REP),
                              (WRONG_REQ,  WRONG_REP)]:
        answer = sio_sock.write(request)
        assert sio_sock.connected
        assert sio_sock.connection_counter == 1
        assert answer is None
        reply = sio_sock.readline()
        assert expected == reply


def test_readuntil(sio_sock):
    for request, expected in [(IDN_REQ,  IDN_REP),
                              (WRONG_REQ,  WRONG_REP)]:
        answer = sio_sock.write(request)
        assert sio_sock.connected
        assert sio_sock.connection_counter == 1
        assert answer is None
        reply = sio_sock.readuntil(b'\n')
        assert expected == reply


def test_readexactly(sio_sock):
    for request, expected in [(IDN_REQ,  IDN_REP),
                              (WRONG_REQ,  WRONG_REP)]:
        answer = sio_sock.write(request)
        assert sio_sock.connected
        assert sio_sock.connection_counter == 1
        assert answer is None
        reply = sio_sock.readexactly(len(expected) - 5)
        assert expected[:-5] == reply
        reply = sio_sock.readexactly(5)
        assert expected[-5:] == reply


def test_readlines(sio_sock):
    for request, expected in [(IDN_REQ,  [IDN_REP]), (2*IDN_REQ,  2*[IDN_REP]),
                              (IDN_REQ + WRONG_REQ,  [IDN_REP, WRONG_REP])]:
        answer = sio_sock.write(request)
        assert sio_sock.connected
        assert sio_sock.connection_counter == 1
        assert answer is None
        gen = sio_sock.readlines(len(expected))
        reply = [line for line in gen]
        assert expected == reply


def test_read(sio_sock):
    for request, expected in [(IDN_REQ,  IDN_REP),
                              (WRONG_REQ,  WRONG_REP)]:
        answer = sio_sock.write(request)
        assert sio_sock.connected
        assert sio_sock.connection_counter == 1
        assert answer is None
        reply, n = b'', 0
        while len(reply) < len(expected) and n < 2:
            reply += sio_sock.read(1024)
            n += 1
        assert expected == reply
