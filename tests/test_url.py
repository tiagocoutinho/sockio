import asyncio

import pytest

from sockio import socket_for_url

from conftest import IDN_REQ, IDN_REP


@pytest.mark.asyncio
async def test_root_socket_for_url(aio_server):
    host, port = aio_server.sockets[0].getsockname()

    with pytest.raises(ValueError):
        socket_for_url("udp://{}:{}".format(host, port))

    aio_tcp = socket_for_url("tcp://{}:{}".format(host, port))

    assert not aio_tcp.connected()
    assert aio_tcp.connection_counter == 0

    await aio_tcp.open()
    assert aio_tcp.connected()
    assert aio_tcp.connection_counter == 1

    coro = aio_tcp.write_readline(IDN_REQ)
    assert asyncio.iscoroutine(coro)
    reply = await coro
    assert aio_tcp.connected()
    assert aio_tcp.connection_counter == 1
    assert reply == IDN_REP


def test_root_socket_for_url_sync(sio_server):
    host, port = sio_server.sockets[0].getsockname()

    with pytest.raises(ValueError):
        socket_for_url("udp://{}:{}".format(host, port), concurrency="sync")

    aio_tcp = socket_for_url("tcp://{}:{}".format(host, port), concurrency="sync")

    assert not aio_tcp.connected()
    assert aio_tcp.connection_counter == 0

    aio_tcp.open()
    assert aio_tcp.connected()
    assert aio_tcp.connection_counter == 1

    reply = aio_tcp.write_readline(IDN_REQ)
    assert aio_tcp.connected()
    assert aio_tcp.connection_counter == 1
    assert reply == IDN_REP


def test_root_socket_for_url_error(sio_server):
    host, port = sio_server.sockets[0].getsockname()

    with pytest.raises(ValueError):
        socket_for_url("udp://{}:{}".format(host, port))

    with pytest.raises(ValueError):
        socket_for_url("udp://{}:{}".format(host, port), concurrency="async")

    with pytest.raises(ValueError):
        socket_for_url("tcp://{}:{}".format(host, port), concurrency="parallel")
