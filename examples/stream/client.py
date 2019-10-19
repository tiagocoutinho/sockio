import asyncio
import logging

import sockio.aio


async def main():
    event = asyncio.Event()
    s = sockio.aio.Socket('localhost', 12345, on_eof_received=event.set)
    async for line in s:
        print(line)
    await s.close()


fmt = '%(asctime)-15s %(levelname)-5s %(name)s: %(message)s'
logging.basicConfig(format=fmt, level=logging.DEBUG)


try:
    if hasattr(asyncio, 'run'):
        asyncio.run(main())
    else:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
except KeyboardInterrupt:
    print('Ctrl-C pressed. Bailing out!')
