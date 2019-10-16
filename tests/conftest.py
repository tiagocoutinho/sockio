import asyncio

import pytest

import sockio.aio


@pytest.fixture()
async def server():
    async def cb(reader, writer):
        try:
            while True:
                data = await reader.readline()
                if data.upper() == b'*IDN?\n':
                    msg = b'ACME, bla ble ble, 1234, 5678\n'
                else:
                    msg = b'ERROR: unknown command\n'
                # TODO: figure out why putting sleep where triggers:
                # "Task was destroyed but it is pending!" messages
                # await asyncio.sleep(0.1)
                writer.write(msg)
                await writer.drain()
        except:
            pass

    server = await asyncio.start_server(cb, host='0')
    task = asyncio.create_task(server.serve_forever())
    yield server
    server.close()


@pytest.fixture
async def aio_sock(server):
    addr = server.sockets[0].getsockname()
    sock = sockio.aio.Socket(*addr)
    yield sock
    await sock.close()
