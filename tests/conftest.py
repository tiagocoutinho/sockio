import queue
import asyncio

import pytest

import sockio.aio
import sockio.sio
import sockio.py2


IDN_REQ, IDN_REP = b"*idn?\n", b"ACME, bla ble ble, 1234, 5678\n"
WRONG_REQ, WRONG_REP = b"wrong question\n", b"ERROR: unknown command\n"


async def server_coro(start_serving=True):
    writers = set()

    async def cb(reader, writer):
        writers.add(writer)
        try:
            while True:
                data = await reader.readline()
                if data.lower() == IDN_REQ:
                    msg = IDN_REP
                elif data.lower().startswith(b"data?"):
                    n = int(data.strip().split(b" ", 1)[-1])
                    for i in range(n):
                        await asyncio.sleep(0.05)
                        writer.write(b"1.2345 5.4321 12345.54321\n")
                        await writer.drain()
                    writer.close()
                    await writer.wait_closed()
                    return
                elif not data:
                    writer.close()
                    await writer.wait_closed()
                    return
                else:
                    msg = WRONG_REP
                # add 2ms delay
                await asyncio.sleep(0.002)
                writer.write(msg)
                await writer.drain()
        except ConnectionResetError:
            pass
        finally:
            writers.remove(writer)

    async def stop():
        server.close()
        await server.wait_closed()
        assert not server.is_serving()
        for writer in set(writers):
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(cb, host="0", start_serving=start_serving)
    server.stop = stop
    return server


@pytest.fixture
async def aio_server():
    server = await server_coro()
    yield server
    await server.stop()


@pytest.fixture
async def aio_tcp(aio_server):
    addr = aio_server.sockets[0].getsockname()
    sock = sockio.aio.TCP(*addr)
    yield sock
    await sock.close()


@pytest.fixture
def sio_server():
    event_loop = sockio.sio.DefaultEventLoop
    channel = queue.Queue()

    async def serve_forever():
        server = await server_coro(start_serving=False)
        channel.put(server)
        await server.serve_forever()
        await server.stop()

    event_loop.run_coroutine(serve_forever())
    server = event_loop.proxy(channel.get())
    yield server
    server.close()


@pytest.fixture
def sio_tcp(sio_server):
    addr = sio_server.sockets[0].getsockname()
    sock = sockio.sio.TCP(*addr)
    yield sock
    sock.close()


@pytest.fixture
def py2_tcp(sio_server):
    addr = sio_server.sockets[0].getsockname()
    sock = sockio.py2.TCP(*addr)
    yield sock
    sock.close()
