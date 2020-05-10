import asyncio
import logging

import sockio.aio


async def main():
    event = asyncio.Event()
    s = sockio.aio.TCP("localhost", 12345, on_eof_received=event.set)
    reply = await s.write_readline(b"*idn?\n")
    print("Server replies with: {!r}".format(reply))
    print("Looks like the server is running. Great!")
    print("Now, please restart the server...")
    await event.wait()
    print("Thanks for turning it off!")
    print("You now have 5s to turn it back on again.")
    await asyncio.sleep(5)
    print("I will now try another request without explicitly reopening the socket")
    reply = await s.write_readline(b"*idn?\n")
    print("It works! Server replies with: {!r}".format(reply))
    await s.close()


fmt = "%(asctime)-15s %(levelname)-5s %(name)s: %(message)s"
logging.basicConfig(format=fmt)

try:
    if hasattr(asyncio, "run"):
        asyncio.run(main())
    else:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
except KeyboardInterrupt:
    print("Ctrl-C pressed. Bailing out!")
