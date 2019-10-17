import os
import sys
import inspect
import subprocess
import asyncio.subprocess

import pytest

from sockio.aio import Socket

from conftest import IDN_REQ, IDN_REP, WRONG_REQ, WRONG_REP


def test_socket_creation():
    sock = Socket('example.com', 34567)
    assert sock.host == 'example.com'
    assert sock.port == 34567
    assert sock.auto_reconnect == True
    assert not sock.connected
    assert sock.connection_counter == 0

@pytest.mark.asyncio
async def test_open_fail(unused_tcp_port):
    sock = Socket('0', unused_tcp_port)
    assert not sock.connected
    assert sock.connection_counter == 0

    with pytest.raises(ConnectionRefusedError):
        await sock.open()
    assert not sock.connected
    assert sock.connection_counter == 0

@pytest.mark.asyncio
async def test_write_fail(unused_tcp_port):
    sock = Socket('0', unused_tcp_port)
    assert not sock.connected
    assert sock.connection_counter == 0

    with pytest.raises(ConnectionRefusedError):
        await sock.write(IDN_REQ)
    assert not sock.connected
    assert sock.connection_counter == 0

@pytest.mark.asyncio
async def test_write_readline_fail(unused_tcp_port):
    sock = Socket('0', unused_tcp_port)
    assert not sock.connected
    assert sock.connection_counter == 0

    with pytest.raises(ConnectionRefusedError):
        await sock.write_readline(IDN_REQ)
    assert not sock.connected
    assert sock.connection_counter == 0


@pytest.mark.asyncio
async def test_open_close(aio_server, aio_sock):
    assert not aio_sock.connected
    assert aio_server.sockets[0].getsockname() == (aio_sock.host, aio_sock.port)

    await aio_sock.open()
    assert aio_sock.connected
    assert aio_sock.connection_counter == 1

    with pytest.raises(ConnectionError):
        await aio_sock.open()
    assert aio_sock.connected
    assert aio_sock.connection_counter == 1

    await aio_sock.close()
    assert not aio_sock.connected
    assert aio_sock.connection_counter == 1
    await aio_sock.open()
    assert aio_sock.connected
    assert aio_sock.connection_counter == 2
    await aio_sock.close()
    await aio_sock.close()
    assert not aio_sock.connected
    assert aio_sock.connection_counter == 2

@pytest.mark.asyncio
async def test_write_readline(aio_sock):
    for request, expected in [(IDN_REQ,  IDN_REP),
                              (WRONG_REQ,  WRONG_REP)]:
        coro = aio_sock.write_readline(request)
        assert asyncio.iscoroutine(coro)
        reply = await coro
        assert aio_sock.connected
        assert aio_sock.connection_counter == 1
        assert expected == reply


@pytest.mark.asyncio
async def test_write_readlines(aio_sock):
    for request, expected in [(IDN_REQ,  [IDN_REP]), (2*IDN_REQ,  2*[IDN_REP]),
                              (IDN_REQ + WRONG_REQ,  [IDN_REP, WRONG_REP])]:
        async_gen = aio_sock.write_readlines(request, len(expected))
        assert inspect.isasyncgen(async_gen)
        reply = [line async for line in async_gen]
        assert aio_sock.connected
        assert aio_sock.connection_counter == 1
        assert expected == reply


@pytest.mark.asyncio
async def test_writelines_readlines(aio_sock):
    for request, expected in [([IDN_REQ],  [IDN_REP]), (2*[IDN_REQ],  2*[IDN_REP]),
                              ([IDN_REQ, WRONG_REQ],  [IDN_REP, WRONG_REP])]:
        async_gen = aio_sock.writelines_readlines(request)
        assert inspect.isasyncgen(async_gen)
        reply = [line async for line in async_gen]
        assert aio_sock.connected
        assert aio_sock.connection_counter == 1
        assert expected == reply


@pytest.mark.asyncio
async def test_writelines(aio_sock):
    for request, expected in [([IDN_REQ],  [IDN_REP]), (2*[IDN_REQ],  2*[IDN_REP]),
                              ([IDN_REQ, WRONG_REQ],  [IDN_REP, WRONG_REP])]:
        coro = aio_sock.writelines(request)
        assert asyncio.iscoroutine(coro)
        answer = await coro
        assert aio_sock.connected
        assert aio_sock.connection_counter == 1
        assert answer is None

        async_gen = aio_sock.readlines(len(expected))
        assert inspect.isasyncgen(async_gen)
        reply = [line async for line in async_gen]
        assert aio_sock.connected
        assert aio_sock.connection_counter == 1
        assert expected == reply


@pytest.mark.asyncio
async def test_readline(aio_sock):
    for request, expected in [(IDN_REQ,  IDN_REP),
                              (WRONG_REQ,  WRONG_REP)]:
        coro = aio_sock.write(request)
        assert asyncio.iscoroutine(coro)
        answer = await coro
        assert aio_sock.connected
        assert aio_sock.connection_counter == 1
        assert answer is None
        coro = aio_sock.readline()
        assert asyncio.iscoroutine(coro)
        reply = await coro
        assert expected == reply


@pytest.mark.asyncio
async def test_readuntil(aio_sock):
    for request, expected in [(IDN_REQ,  IDN_REP),
                              (WRONG_REQ,  WRONG_REP)]:
        coro = aio_sock.write(request)
        assert asyncio.iscoroutine(coro)
        answer = await coro
        assert aio_sock.connected
        assert aio_sock.connection_counter == 1
        assert answer is None
        coro = aio_sock.readuntil(b'\n')
        assert asyncio.iscoroutine(coro)
        reply = await coro
        assert expected == reply


@pytest.mark.asyncio
async def test_readexactly(aio_sock):
    for request, expected in [(IDN_REQ,  IDN_REP),
                              (WRONG_REQ,  WRONG_REP)]:
        coro = aio_sock.write(request)
        assert asyncio.iscoroutine(coro)
        answer = await coro
        assert aio_sock.connected
        assert aio_sock.connection_counter == 1
        assert answer is None
        coro = aio_sock.readexactly(len(expected) - 5)
        assert asyncio.iscoroutine(coro)
        reply = await coro
        assert expected[:-5] == reply
        coro = aio_sock.readexactly(5)
        assert asyncio.iscoroutine(coro)
        reply = await coro
        assert expected[-5:] == reply


@pytest.mark.asyncio
async def test_readlines(aio_sock):
    for request, expected in [(IDN_REQ,  [IDN_REP]), (2*IDN_REQ,  2*[IDN_REP]),
                              (IDN_REQ + WRONG_REQ,  [IDN_REP, WRONG_REP])]:
        coro = aio_sock.write(request)
        assert asyncio.iscoroutine(coro)
        answer = await coro
        assert aio_sock.connected
        assert aio_sock.connection_counter == 1
        assert answer is None
        async_gen = aio_sock.readlines(len(expected))
        assert inspect.isasyncgen(async_gen)
        reply = [line async for line in async_gen]
        assert expected == reply


@pytest.mark.asyncio
async def test_read(aio_sock):
    for request, expected in [(IDN_REQ,  IDN_REP),
                              (WRONG_REQ,  WRONG_REP)]:
        coro = aio_sock.write(request)
        assert asyncio.iscoroutine(coro)
        answer = await coro
        assert aio_sock.connected
        assert aio_sock.connection_counter == 1
        assert answer is None
        reply, n = b'', 0
        while len(reply) < len(expected) and n < 2:
            coro = aio_sock.read(1024)
            assert asyncio.iscoroutine(coro)
            reply += await coro
            n += 1
        assert expected == reply


@pytest.mark.skipif(os.environ.get('CONDA_SHLVL', '0') != '0', reason='Inside conda environment')
async def test_cli(aio_server):
    _, port = aio_server.sockets[0].getsockname()
    proc = await asyncio.create_subprocess_exec(
        sys.executable, '-m', 'sockio.aio', '--port', str(port),
        stdout=asyncio.subprocess.PIPE)
    await proc.wait()
    result = await proc.stdout.readline()
    assert result == IDN_REP
