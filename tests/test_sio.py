import pytest

from sockio.sio import TCP, main

from conftest import IDN_REQ, IDN_REP, WRONG_REQ, WRONG_REP


def test_socket_creation():
    sock = TCP('example.com', 34567)
    assert sock.host == 'example.com'
    assert sock.port == 34567
    assert sock.auto_reconnect == True
    assert not sock.connected
    assert sock.connection_counter == 0


def test_open_fail(unused_tcp_port):
    sock = TCP('0', unused_tcp_port)
    assert not sock.connected
    assert sock.connection_counter == 0

    with pytest.raises(ConnectionRefusedError):
        sock.open()
    assert not sock.connected
    assert sock.connection_counter == 0


def test_write_fail(unused_tcp_port):
    sock = TCP('0', unused_tcp_port)
    assert not sock.connected
    assert sock.connection_counter == 0

    with pytest.raises(ConnectionRefusedError):
        sock.write(IDN_REQ)
    assert not sock.connected
    assert sock.connection_counter == 0


def test_write_readline_fail(unused_tcp_port):
    sock = TCP('0', unused_tcp_port)
    assert not sock.connected
    assert sock.connection_counter == 0

    with pytest.raises(ConnectionRefusedError):
        sock.write_readline(IDN_REQ)
    assert not sock.connected
    assert sock.connection_counter == 0


def test_open_close(sio_server, sio_tcp):
    assert not sio_tcp.connected
    assert sio_tcp.connection_counter == 0
    assert sio_server.sockets[0].getsockname() == (sio_tcp.host, sio_tcp.port)

    sio_tcp.open()
    assert sio_tcp.connected
    assert sio_tcp.connection_counter == 1

    with pytest.raises(ConnectionError):
        sio_tcp.open()
    assert sio_tcp.connected
    assert sio_tcp.connection_counter == 1

    sio_tcp.close()
    assert not sio_tcp.connected
    assert sio_tcp.connection_counter == 1
    sio_tcp.open()
    assert sio_tcp.connected
    assert sio_tcp.connection_counter == 2
    sio_tcp.close()
    sio_tcp.close()
    assert not sio_tcp.connected
    assert sio_tcp.connection_counter == 2


@pytest.mark.asyncio
async def test_callbacks(sio_server):
    host, port = sio_server.sockets[0].getsockname()
    state = dict(made=0, lost=0, eof=0)

    def made():
        state['made'] += 1

    def lost(exc):
        state['lost'] += 1

    def eof():
        state['eof'] += 1

    sio_tcp = TCP(host, port, on_connection_made=made,
                   on_connection_lost=lost, on_eof_received=eof)
    assert not sio_tcp.connected
    assert sio_tcp.connection_counter == 0
    assert state['made'] == 0
    assert state['lost'] == 0
    assert state['eof'] == 0

    sio_tcp.open()
    assert sio_tcp.connected
    assert sio_tcp.connection_counter == 1
    assert state['made'] == 1
    assert state['lost'] == 0
    assert state['eof'] == 0

    with pytest.raises(ConnectionError):
        sio_tcp.open()
    assert sio_tcp.connected
    assert sio_tcp.connection_counter == 1
    assert state['made'] == 1
    assert state['lost'] == 0
    assert state['eof'] == 0

    sio_tcp.close()
    assert not sio_tcp.connected
    assert sio_tcp.connection_counter == 1
    assert state['made'] == 1
    assert state['lost'] == 1
    assert state['eof'] == 0

    sio_tcp.open()
    assert sio_tcp.connected
    assert sio_tcp.connection_counter == 2
    assert state['made'] == 2
    assert state['lost'] == 1
    assert state['eof'] == 0

    sio_tcp.close()
    assert not sio_tcp.connected
    assert sio_tcp.connection_counter == 2
    assert state['made'] == 2
    assert state['lost'] == 2
    assert state['eof'] == 0

    sio_tcp.close()
    assert not sio_tcp.connected
    assert sio_tcp.connection_counter == 2
    assert state['made'] == 2
    assert state['lost'] == 2
    assert state['eof'] == 0


def test_write_readline(sio_tcp):
    for request, expected in [(IDN_REQ,  IDN_REP),
                              (WRONG_REQ,  WRONG_REP)]:
        reply = sio_tcp.write_readline(request)
        assert sio_tcp.connected
        assert sio_tcp.connection_counter == 1
        assert expected == reply


def test_write_readlines(sio_tcp):
    for request, expected in [(IDN_REQ,  [IDN_REP]), (2*IDN_REQ,  2*[IDN_REP]),
                              (IDN_REQ + WRONG_REQ,  [IDN_REP, WRONG_REP])]:
        gen = sio_tcp.write_readlines(request, len(expected))
        reply = [line for line in gen]
        assert sio_tcp.connected
        assert sio_tcp.connection_counter == 1
        assert expected == reply


def test_writelines_readlines(sio_tcp):
    for request, expected in [([IDN_REQ],  [IDN_REP]), (2*[IDN_REQ],  2*[IDN_REP]),
                              ([IDN_REQ, WRONG_REQ],  [IDN_REP, WRONG_REP])]:
        gen = sio_tcp.writelines_readlines(request)
        reply = [line for line in gen]
        assert sio_tcp.connected
        assert sio_tcp.connection_counter == 1
        assert expected == reply


def test_writelines(sio_tcp):
    for request, expected in [([IDN_REQ],  [IDN_REP]), (2*[IDN_REQ],  2*[IDN_REP]),
                              ([IDN_REQ, WRONG_REQ],  [IDN_REP, WRONG_REP])]:
        answer = sio_tcp.writelines(request)
        assert sio_tcp.connected
        assert sio_tcp.connection_counter == 1
        assert answer is None

        gen = sio_tcp.readlines(len(expected))
        reply = [line for line in gen]
        assert sio_tcp.connected
        assert sio_tcp.connection_counter == 1
        assert expected == reply


def test_readline(sio_tcp):
    for request, expected in [(IDN_REQ,  IDN_REP),
                              (WRONG_REQ,  WRONG_REP)]:
        answer = sio_tcp.write(request)
        assert sio_tcp.connected
        assert sio_tcp.connection_counter == 1
        assert answer is None
        reply = sio_tcp.readline()
        assert expected == reply


def test_readuntil(sio_tcp):
    for request, expected in [(IDN_REQ,  IDN_REP),
                              (WRONG_REQ,  WRONG_REP)]:
        answer = sio_tcp.write(request)
        assert sio_tcp.connected
        assert sio_tcp.connection_counter == 1
        assert answer is None
        reply = sio_tcp.readuntil(b'\n')
        assert expected == reply


def test_readexactly(sio_tcp):
    for request, expected in [(IDN_REQ,  IDN_REP),
                              (WRONG_REQ,  WRONG_REP)]:
        answer = sio_tcp.write(request)
        assert sio_tcp.connected
        assert sio_tcp.connection_counter == 1
        assert answer is None
        reply = sio_tcp.readexactly(len(expected) - 5)
        assert expected[:-5] == reply
        reply = sio_tcp.readexactly(5)
        assert expected[-5:] == reply


def test_readlines(sio_tcp):
    for request, expected in [(IDN_REQ,  [IDN_REP]), (2*IDN_REQ,  2*[IDN_REP]),
                              (IDN_REQ + WRONG_REQ,  [IDN_REP, WRONG_REP])]:
        answer = sio_tcp.write(request)
        assert sio_tcp.connected
        assert sio_tcp.connection_counter == 1
        assert answer is None
        gen = sio_tcp.readlines(len(expected))
        reply = [line for line in gen]
        assert expected == reply


def test_read(sio_tcp):
    for request, expected in [(IDN_REQ,  IDN_REP),
                              (WRONG_REQ,  WRONG_REP)]:
        answer = sio_tcp.write(request)
        assert sio_tcp.connected
        assert sio_tcp.connection_counter == 1
        assert answer is None
        reply, n = b'', 0
        while len(reply) < len(expected) and n < 2:
            reply += sio_tcp.read(1024)
            n += 1
        assert expected == reply


@pytest.mark.skip('would block')
def test_cli(aio_server, capsys):
    _, port = aio_server.sockets[0].getsockname()
    main(['--port', str(port)])
    captured = capsys.readouterr()
    assert captured.out == repr(IDN_REP) + '\n'
