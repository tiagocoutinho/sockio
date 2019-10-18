import queue
import asyncio

import pytest

import sockio.aio
import sockio.sio


IDN_REQ, IDN_REP = b'*idn?\n', b'ACME, bla ble ble, 1234, 5678\n'
WRONG_REQ, WRONG_REP = b'wrong question\n', b'ERROR: unknown command\n'


def server_coro():
    data = dict(nb_clients=0)
    async def cb(reader, writer):
        try:
            while True:
                data = await reader.readline()
                if data.lower() == IDN_REQ:
                    msg = IDN_REP
                else:
                    msg = WRONG_REP
                # add 2ms delay
                await asyncio.sleep(0.002)
                writer.write(msg)
                await writer.drain()
        except Exception:
            pass

    return asyncio.start_server(cb, host='0')


@pytest.fixture()
async def aio_server():
    server = await server_coro()
    asyncio.create_task(server.serve_forever())
    yield server
    server.close()
    await server.wait_closed()
    assert not server.is_serving()


@pytest.fixture
async def aio_sock(aio_server):
    addr = aio_server.sockets[0].getsockname()
    sock = sockio.aio.Socket(*addr)
    yield sock
    await sock.close()


@pytest.fixture()
def sio_server():
    event_loop = sockio.sio.DefaultEventLoop
    channel = queue.Queue()
    async def serve_forever():
        server = await server_coro()
        channel.put(server)
        await server.serve_forever()
    event_loop.run_coroutine(serve_forever())
    server = event_loop.proxy(channel.get())
    yield server
    server.close()


@pytest.fixture
def sio_sock(sio_server):
    addr = sio_server.sockets[0].getsockname()
    sock = sockio.sio.Socket(*addr)
    yield sock
    sock.close()
