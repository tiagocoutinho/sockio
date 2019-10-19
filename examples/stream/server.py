import asyncio
import logging


async def run(options):
    async def cb(reader, writer):
        addr = writer.transport.get_extra_info('peername')
        logging.info('client connected from %s', addr)
        try:
            for i in range(10):
                msg = f'message {i}\n'
                writer.write(msg.encode())
                await writer.drain()
                logging.debug('send %r', msg)
                await asyncio.sleep(1)
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

    server = await asyncio.start_server(
        cb, host=options.host, port=options.port)
    host, port = server.sockets[0].getsockname()
    logging.info('started accepting requests on %s:%d', host, port)
    async with server:
        await server.serve_forever()


def main(args=None):
    import argparse
    parser = argparse.ArgumentParser()
    log_level_choices = ["critical", "error", "warning", "info", "debug"]
    log_level_choices += [i.upper() for i in log_level_choices]
    parser.add_argument('--host', default='0',
                        help='SCPI bind address')
    parser.add_argument('-p', '--port', type=int, help='SCPI server port')
    parser.add_argument("--log-level", choices=log_level_choices,
                        default="warning")
    parser.add_argument('-d', '--debug', action='store_true')
    options = parser.parse_args(args)
    fmt = '%(asctime)-15s %(levelname)-5s: %(message)s'
    logging.basicConfig(level=options.log_level.upper(), format=fmt)
    try:
        asyncio.run(run(options))
    except KeyboardInterrupt:
        logging.info('Ctrl-C pressed. Bailing out!')


if __name__ == '__main__':
    main()

