import sys
import asyncio
import logging

IDN_REQ, IDN_REP = b"*idn?\n", b"ACME, bla ble ble, 1234, 5678\n"
WRONG_REQ, WRONG_REP = b"wrong question\n", b"ERROR: unknown command\n"


PY_37 = sys.version_info >= (3, 7)


async def run(options):
    async def cb(reader, writer):
        addr = writer.transport.get_extra_info("peername")
        logging.info("client connected from %s", addr)
        try:
            while True:
                data = await reader.readline()
                if data.lower() == IDN_REQ:
                    msg = IDN_REP
                elif not data:
                    logging.info("client %s disconnected", addr)
                    return
                else:
                    msg = WRONG_REP
                logging.debug("recv %r", data)
                writer.write(msg)
                await writer.drain()
                logging.debug("send %r", msg)
        except Exception:
            writer.close()
            if PY_37:
                await writer.wait_closed()

    server = await asyncio.start_server(cb, host=options.host, port=options.port)
    host, port = server.sockets[0].getsockname()
    logging.info("started accepting requests on %s:%d", host, port)
    async with server:
        await server.serve_forever()


def main(args=None):
    import argparse

    parser = argparse.ArgumentParser()
    log_level_choices = ["critical", "error", "warning", "info", "debug"]
    log_level_choices += [i.upper() for i in log_level_choices]
    parser.add_argument("--host", default="0", help="SCPI bind address")
    parser.add_argument("-p", "--port", type=int, help="SCPI server port")
    parser.add_argument("--log-level", choices=log_level_choices, default="warning")
    parser.add_argument("-d", "--debug", action="store_true")
    options = parser.parse_args(args)
    fmt = "%(asctime)-15s %(levelname)-5s: %(message)s"
    logging.basicConfig(level=options.log_level.upper(), format=fmt)
    try:
        coro = run(options)
        if hasattr(asyncio, "run"):
            asyncio.run(coro)
        else:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(coro)
    except KeyboardInterrupt:
        logging.info("Ctrl-C pressed. Bailing out!")


if __name__ == "__main__":
    main()
