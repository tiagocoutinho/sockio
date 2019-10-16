import asyncio

import pytest

from sockio.aio import Socket


def test_socket_creation():
    sock = Socket('example.com', 34567)
    assert sock.host == 'example.com'
    assert sock.port == 34567
    assert sock.auto_reconnect == True
    assert not sock.connected


@pytest.mark.asyncio
async def test_open_fail(unused_tcp_port):
    sock = Socket('0', unused_tcp_port)
    assert not sock.connected

    with pytest.raises(ConnectionRefusedError):
        await sock.open()
    assert not sock.connected


@pytest.mark.asyncio
async def test_write_fail(unused_tcp_port):
    sock = Socket('0', unused_tcp_port)
    assert not sock.connected

    with pytest.raises(ConnectionRefusedError):
        await sock.write(b'*idn?\n')
    assert not sock.connected


@pytest.mark.asyncio
async def test_write_readline_fail(unused_tcp_port):
    sock = Socket('0', unused_tcp_port)
    assert not sock.connected

    with pytest.raises(ConnectionRefusedError):
        await sock.write_readline(b'*idn?\n')
    assert not sock.connected


@pytest.mark.asyncio
async def test_open_close(server, aio_sock):
    assert not aio_sock.connected
    await aio_sock.open()
    assert aio_sock.connected

    with pytest.raises(ConnectionError):
        await aio_sock.open()
    assert aio_sock.connected

    await aio_sock.close()
    assert not aio_sock.connected
    await aio_sock.open()
    assert aio_sock.connected
    await aio_sock.close()
    await aio_sock.close()
    assert not aio_sock.connected


@pytest.mark.asyncio
async def test_write_readline(server, aio_sock):
    assert not aio_sock.connected
    assert server.sockets[0].getsockname() == (aio_sock.host, aio_sock.port)

    for request, expected in [(b'*idn?\n',  b'ACME, bla ble ble, 1234, 5678\n'),
                              (b'wrong question\n',  b'ERROR: unknown command\n')]:
        coro = aio_sock.write_readline(request)
        assert asyncio.iscoroutine(coro)
        reply = await coro
        assert aio_sock.connected
        assert expected == reply


@pytest.mark.asyncio
async def test_readline(server, aio_sock):
    assert not aio_sock.connected
    assert server.sockets[0].getsockname() == (aio_sock.host, aio_sock.port)

    for request, expected in [(b'*idn?\n',  b'ACME, bla ble ble, 1234, 5678\n'),
                              (b'wrong question\n',  b'ERROR: unknown command\n')]:
        coro = aio_sock.write(request)
        assert asyncio.iscoroutine(coro)
        answer = await coro
        assert aio_sock.connected
        assert answer is None
        coro = aio_sock.readline()
        assert asyncio.iscoroutine(coro)
        reply = await coro
        assert expected == reply


@pytest.mark.asyncio
async def test_read(server, aio_sock):
    assert not aio_sock.connected
    assert server.sockets[0].getsockname() == (aio_sock.host, aio_sock.port)

    for request, expected in [(b'*idn?\n',  b'ACME, bla ble ble, 1234, 5678\n'),
                              (b'wrong question\n',  b'ERROR: unknown command\n')]:
        coro = aio_sock.write(request)
        assert asyncio.iscoroutine(coro)
        answer = await coro
        assert aio_sock.connected
        assert answer is None
        reply, n = b'', 0
        while len(reply) < len(expected) and n < 2:
            coro = aio_sock.read(1024)
            assert asyncio.iscoroutine(coro)
            reply += await coro
            n += 1
        assert expected == reply
