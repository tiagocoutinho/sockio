import os
import sys
import subprocess
import asyncio.subprocess

import pytest

from sockio.aio import TCP, main

from conftest import IDN_REQ, IDN_REP, WRONG_REQ, WRONG_REP


def test_socket_creation():
    sock = TCP('example.com', 34567)
    assert sock.host == 'example.com'
    assert sock.port == 34567
    assert sock.auto_reconnect == True
    assert not sock.connected
    assert sock.connection_counter == 0

@pytest.mark.asyncio
async def test_open_fail(unused_tcp_port):
    sock = TCP('0', unused_tcp_port)
    assert not sock.connected
    assert sock.connection_counter == 0

    with pytest.raises(ConnectionRefusedError):
        await sock.open()
    assert not sock.connected
    assert sock.connection_counter == 0

@pytest.mark.asyncio
async def test_write_fail(unused_tcp_port):
    sock = TCP('0', unused_tcp_port)
    assert not sock.connected
    assert sock.connection_counter == 0

    with pytest.raises(ConnectionRefusedError):
        await sock.write(IDN_REQ)
    assert not sock.connected
    assert sock.connection_counter == 0

@pytest.mark.asyncio
async def test_write_readline_fail(unused_tcp_port):
    sock = TCP('0', unused_tcp_port)
    assert not sock.connected
    assert sock.connection_counter == 0

    with pytest.raises(ConnectionRefusedError):
        await sock.write_readline(IDN_REQ)
    assert not sock.connected
    assert sock.connection_counter == 0


@pytest.mark.asyncio
async def test_open_close(aio_server, aio_tcp):
    assert not aio_tcp.connected
    assert aio_tcp.connection_counter == 0
    assert aio_server.sockets[0].getsockname() == (aio_tcp.host, aio_tcp.port)

    await aio_tcp.open()
    assert aio_tcp.connected
    assert aio_tcp.connection_counter == 1

    with pytest.raises(ConnectionError):
        await aio_tcp.open()
    assert aio_tcp.connected
    assert aio_tcp.connection_counter == 1

    await aio_tcp.close()
    assert not aio_tcp.connected
    assert aio_tcp.connection_counter == 1
    await aio_tcp.open()
    assert aio_tcp.connected
    assert aio_tcp.connection_counter == 2
    await aio_tcp.close()
    await aio_tcp.close()
    assert not aio_tcp.connected
    assert aio_tcp.connection_counter == 2


@pytest.mark.asyncio
async def test_callbacks(aio_server):
    host, port = aio_server.sockets[0].getsockname()
    state = dict(made=0, lost=0, eof=0)

    def made():
        state['made'] += 1

    def lost(exc):
        state['lost'] += 1

    def eof():
        state['eof'] += 1

    aio_tcp = TCP(host, port, on_connection_made=made,
                  on_connection_lost=lost, on_eof_received=eof)
    assert not aio_tcp.connected
    assert aio_tcp.connection_counter == 0
    assert state['made'] == 0
    assert state['lost'] == 0
    assert state['eof'] == 0

    await aio_tcp.open()
    assert aio_tcp.connected
    assert aio_tcp.connection_counter == 1
    assert state['made'] == 1
    assert state['lost'] == 0
    assert state['eof'] == 0

    with pytest.raises(ConnectionError):
        await aio_tcp.open()
    assert aio_tcp.connected
    assert aio_tcp.connection_counter == 1
    assert state['made'] == 1
    assert state['lost'] == 0
    assert state['eof'] == 0

    await aio_tcp.close()
    assert not aio_tcp.connected
    assert aio_tcp.connection_counter == 1
    assert state['made'] == 1
    assert state['lost'] == 1
    assert state['eof'] == 0

    await aio_tcp.open()
    assert aio_tcp.connected
    assert aio_tcp.connection_counter == 2
    assert state['made'] == 2
    assert state['lost'] == 1
    assert state['eof'] == 0

    await aio_tcp.close()
    assert not aio_tcp.connected
    assert aio_tcp.connection_counter == 2
    assert state['made'] == 2
    assert state['lost'] == 2
    assert state['eof'] == 0

    await aio_tcp.close()
    assert not aio_tcp.connected
    assert aio_tcp.connection_counter == 2
    assert state['made'] == 2
    assert state['lost'] == 2
    assert state['eof'] == 0

@pytest.mark.asyncio
async def test_coroutine_callbacks(aio_server):
    host, port = aio_server.sockets[0].getsockname()
    RESP_TIME = 0.02
    state = dict(made=0, lost=0, eof=0)

    async def made():
        await asyncio.sleep(RESP_TIME)
        state['made'] += 1

    async def lost(exc):
        await asyncio.sleep(RESP_TIME)
        state['lost'] += 1

    async def eof():
        await asyncio.sleep(RESP_TIME)
        state['eof'] += 1

    aio_tcp = TCP(host, port, on_connection_made=made,
                  on_connection_lost=lost, on_eof_received=eof)

    assert not aio_tcp.connected
    assert aio_tcp.connection_counter == 0
    assert state['made'] == 0
    assert state['lost'] == 0
    assert state['eof'] == 0

    await aio_tcp.open()
    assert aio_tcp.connected
    assert aio_tcp.connection_counter == 1
    assert state['made'] == 1
    assert state['lost'] == 0
    assert state['eof'] == 0

    with pytest.raises(ConnectionError):
        await aio_tcp.open()
    assert aio_tcp.connected
    assert aio_tcp.connection_counter == 1
    assert state['made'] == 1
    assert state['lost'] == 0
    assert state['eof'] == 0

    await aio_tcp.close()
    assert not aio_tcp.connected
    assert aio_tcp.connection_counter == 1
    assert state['made'] == 1
    assert state['lost'] == 0
    assert state['eof'] == 0
    await asyncio.sleep(RESP_TIME + 0.01)
    assert state['made'] == 1
    assert state['lost'] == 1
    assert state['eof'] == 0

    await aio_tcp.open()
    assert aio_tcp.connected
    assert aio_tcp.connection_counter == 2
    assert state['made'] == 2
    assert state['lost'] == 1
    assert state['eof'] == 0

    await aio_tcp.close()
    assert not aio_tcp.connected
    assert aio_tcp.connection_counter == 2
    assert state['made'] == 2
    assert state['lost'] == 1
    assert state['eof'] == 0
    await asyncio.sleep(RESP_TIME + 0.01)
    assert state['made'] == 2
    assert state['lost'] == 2
    assert state['eof'] == 0

    await aio_tcp.close()
    assert not aio_tcp.connected
    assert aio_tcp.connection_counter == 2
    assert state['made'] == 2
    assert state['lost'] == 2
    assert state['eof'] == 0
    await asyncio.sleep(RESP_TIME + 0.01)
    assert state['made'] == 2
    assert state['lost'] == 2
    assert state['eof'] == 0

@pytest.mark.asyncio
async def test_error_callback(aio_server):
    host, port = aio_server.sockets[0].getsockname()

    state = dict(made=0)

    def error_callback():
        state['made'] += 1
        raise RuntimeError('cannot handle this')

    aio_tcp = TCP(host, port, on_connection_made=error_callback)

    assert not aio_tcp.connected
    assert aio_tcp.connection_counter == 0
    assert state['made'] == 0

    await aio_tcp.open()
    assert aio_tcp.connected
    assert aio_tcp.connection_counter == 1
    assert state['made'] == 1


@pytest.mark.skip('bug in python server.close() ?')
# @pytest.mark.asyncio
async def test_eof_callback(aio_server):
    host, port = aio_server.sockets[0].getsockname()
    state = dict(made=0, lost=0, eof=0)

    def made():
        state['made'] += 1

    def lost(exc):
        state['lost'] += 1

    def eof():
        state['eof'] += 1

    aio_tcp = TCP(host, port, on_connection_made=made,
                  on_connection_lost=lost, on_eof_received=eof)
    assert not aio_tcp.connected
    assert aio_tcp.connection_counter == 0
    assert state['made'] == 0
    assert state['lost'] == 0
    assert state['eof'] == 0

    await aio_tcp.open()
    assert aio_tcp.connected
    assert aio_tcp.connection_counter == 1
    assert state['made'] == 1
    assert state['lost'] == 0
    assert state['eof'] == 0

    aio_server.close()
    await aio_server.wait_closed()
    assert not aio_server.is_serving()

    assert state['made'] == 1
    assert state['lost'] == 0
    assert state['eof'] == 1


@pytest.mark.asyncio
async def test_write_readline(aio_tcp):
    for request, expected in [(IDN_REQ,  IDN_REP),
                              (WRONG_REQ,  WRONG_REP)]:
        coro = aio_tcp.write_readline(request)
        assert asyncio.iscoroutine(coro)
        reply = await coro
        assert aio_tcp.connected
        assert aio_tcp.connection_counter == 1
        assert expected == reply


@pytest.mark.asyncio
async def test_write_readlines(aio_tcp):
    for request, expected in [(IDN_REQ,  [IDN_REP]), (2*IDN_REQ,  2*[IDN_REP]),
                              (IDN_REQ + WRONG_REQ,  [IDN_REP, WRONG_REP])]:
        coro = aio_tcp.write_readlines(request, len(expected))
        assert asyncio.iscoroutine(coro)
        reply = await coro
        assert aio_tcp.connected
        assert aio_tcp.connection_counter == 1
        assert expected == reply


@pytest.mark.asyncio
async def test_writelines_readlines(aio_tcp):
    for request, expected in [([IDN_REQ],  [IDN_REP]), (2*[IDN_REQ],  2*[IDN_REP]),
                              ([IDN_REQ, WRONG_REQ],  [IDN_REP, WRONG_REP])]:
        coro = aio_tcp.writelines_readlines(request)
        assert asyncio.iscoroutine(coro)
        reply = await coro
        assert aio_tcp.connected
        assert aio_tcp.connection_counter == 1
        assert expected == reply


@pytest.mark.asyncio
async def test_writelines(aio_tcp):
    for request, expected in [([IDN_REQ],  [IDN_REP]), (2*[IDN_REQ],  2*[IDN_REP]),
                              ([IDN_REQ, WRONG_REQ],  [IDN_REP, WRONG_REP])]:
        coro = aio_tcp.writelines(request)
        assert asyncio.iscoroutine(coro)
        answer = await coro
        assert aio_tcp.connected
        assert aio_tcp.connection_counter == 1
        assert answer is None

        coro = aio_tcp.readlines(len(expected))
        assert asyncio.iscoroutine(coro)
        reply = await coro
        assert aio_tcp.connected
        assert aio_tcp.connection_counter == 1
        assert expected == reply


@pytest.mark.asyncio
async def test_readline(aio_tcp):
    for request, expected in [(IDN_REQ,  IDN_REP),
                              (WRONG_REQ,  WRONG_REP)]:
        coro = aio_tcp.write(request)
        assert asyncio.iscoroutine(coro)
        answer = await coro
        assert aio_tcp.connected
        assert aio_tcp.connection_counter == 1
        assert answer is None
        coro = aio_tcp.readline()
        assert asyncio.iscoroutine(coro)
        reply = await coro
        assert expected == reply


@pytest.mark.asyncio
async def test_readuntil(aio_tcp):
    for request, expected in [(IDN_REQ,  IDN_REP),
                              (WRONG_REQ,  WRONG_REP)]:
        coro = aio_tcp.write(request)
        assert asyncio.iscoroutine(coro)
        answer = await coro
        assert aio_tcp.connected
        assert aio_tcp.connection_counter == 1
        assert answer is None
        coro = aio_tcp.readuntil(b'\n')
        assert asyncio.iscoroutine(coro)
        reply = await coro
        assert expected == reply


@pytest.mark.asyncio
async def test_readexactly(aio_tcp):
    for request, expected in [(IDN_REQ,  IDN_REP),
                              (WRONG_REQ,  WRONG_REP)]:
        coro = aio_tcp.write(request)
        assert asyncio.iscoroutine(coro)
        answer = await coro
        assert aio_tcp.connected
        assert aio_tcp.connection_counter == 1
        assert answer is None
        coro = aio_tcp.readexactly(len(expected) - 5)
        assert asyncio.iscoroutine(coro)
        reply = await coro
        assert expected[:-5] == reply
        coro = aio_tcp.readexactly(5)
        assert asyncio.iscoroutine(coro)
        reply = await coro
        assert expected[-5:] == reply


@pytest.mark.asyncio
async def test_readlines(aio_tcp):
    for request, expected in [(IDN_REQ,  [IDN_REP]), (2*IDN_REQ,  2*[IDN_REP]),
                              (IDN_REQ + WRONG_REQ,  [IDN_REP, WRONG_REP])]:
        coro = aio_tcp.write(request)
        assert asyncio.iscoroutine(coro)
        answer = await coro
        assert aio_tcp.connected
        assert aio_tcp.connection_counter == 1
        assert answer is None
        coro = aio_tcp.readlines(len(expected))
        assert asyncio.iscoroutine(coro)
        reply = await coro
        assert expected == reply


@pytest.mark.asyncio
async def test_read(aio_tcp):
    for request, expected in [(IDN_REQ,  IDN_REP),
                              (WRONG_REQ,  WRONG_REP)]:
        coro = aio_tcp.write(request)
        assert asyncio.iscoroutine(coro)
        answer = await coro
        assert aio_tcp.connected
        assert aio_tcp.connection_counter == 1
        assert answer is None
        reply, n = b'', 0
        while len(reply) < len(expected) and n < 2:
            coro = aio_tcp.read(1024)
            assert asyncio.iscoroutine(coro)
            reply += await coro
            n += 1
        assert expected == reply


@pytest.mark.asyncio
async def test_parallel(aio_tcp):
    async def wr(request, expected_reply):
        await aio_tcp.write(request)
        reply = await aio_tcp.readline()
        return request, reply, expected_reply

    args = 10 * [(IDN_REQ, IDN_REP), (WRONG_REQ,  WRONG_REP)]
    coros = [wr(*arg) for arg in args]
    result = await asyncio.gather(*coros)
    for req, reply, expected in result:
        assert reply == expected, 'Failed request {}'.format(req)


@pytest.mark.asyncio
async def test_stream(aio_tcp):
    request = b'data? 2\n'
    await aio_tcp.write(request)
    i = 0
    async for line in aio_tcp:
        assert line == b'1.2345 5.4321 12345.54321\n'
        i += 1
    assert i == 2
    assert aio_tcp.connection_counter == 1
    assert not aio_tcp.connected


# @pytest.mark.skipif(os.environ.get('CONDA_SHLVL', '0') != '0', reason='Inside conda environment')
@pytest.mark.asyncio
async def test_cli(aio_server, capsys):
    _, port = aio_server.sockets[0].getsockname()
    await main(['--port', str(port)])
    captured = capsys.readouterr()
    assert captured.out == repr(IDN_REP) + '\n'
