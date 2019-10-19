# sockio

![Pypi version][pypi]

A python concurrency agnostic socket library.

![spec in action](./demo.svg)

Helpful when handling with instrumentation which work over TCP and implement
simple REQ-REP communication protocols (example:
[SCPI](https://en.m.wikipedia.org/wiki/Standard_Commands_for_Programmable_Instruments)).

So far implemented REQ-REP and streaming semantics with auto-reconnection facilites.

Base implementation written in asyncio with support for different concurrency models:

* asyncio
* classic blocking API
* future based API

## Installation

From within your favourite python environment:

```console
pip install sockio
```

## Usage

*asyncio*

```python
import asyncio
from sockio.aio import Socket

async def main():
    sock = Socket('acme.example.com', 5000)
    # Assuming a SCPI complient on the other end we can ask for:
    reply = await sock.write_readline(b'*IDN?\n')
    print(reply)

asyncio.run(main())
```

*classic*

```python
from sockio.sio import Socket

sock = Socket('acme.example.com', 5000)
reply = sock.write_readline(b'*IDN?\n')
print(reply)
```

*concurrent.futures*

```python
from sockio.sio import Socket

sock = Socket('acme.example.com', 5000, resolve_futures=False)
reply = sock.write_readline(b'*IDN?\n').result()
print(reply)
```

## Features

### REQ-REP semantics

Many instruments out there have a Request-Reply protocol. A sockio Socket
provides `write_read` family of methods which simplify communication with
these instruments. These methods are atomic which means different tasks or
threads can safely work with the same socket object (although I would
question myself why would I be doing that in my library/application).

### Auto-reconnection

```python
sock = Socket('acme.example.com', 5000)
reply = await sock.write_readline(b'*IDN?\n')
print(reply)

# ... kill the server connection somehow and bring it back to life again

# You can use the same socket object. It will reconnect automatically
# and work "transparently"
reply = await sock.write_readline(b'*IDN?\n')
print(reply)
```

The auto-reconnection facility is specially useful when, for example, you
move equipement from one place to another, or you need to turn off the
equipment during the night (planet Earth thanks you for saving energy!).

### Custom EOL

In line based protocols, sometimes people decide `\n` is not a good EOL character.
A sockio Socket can be customized with a different EOL character. Example:

```python
sock = Socket('acme.example.com', 5000, eol=b'\r')
```

The EOL character can be overwritten in any of the `readline` methods. Example:
```python
await sock.write_readline(b'*IDN?\n', eol=b'\r')
```

### Connection event callbacks

You can be notified on `connection_made`, `connection_lost` and `eof_received` events
by registering callbacks on the sockio Socket constructor

This is particularly useful if, for example, you want a specific procedure to be
executed every time the socket is reconnected to make sure your configuration is
right. Example:

```python
async def connected():
    await sock.write(b'ACQU:TRIGGER HARDWARE\n')
    await sock.write(b'DISPLAY OFF\n')

sock = Socket('acme.example.com', 5000, on_connection_made=connected)
```

(see examples/req-rep/client.py)

### Streams

sockio Sockets are asynchronous iterable objects. This means that line streaming
is as easy as:

```python
sock = Socket('acme.example.com', 5000, eol=b'\r')

async for line in sock:
    print(line)
```

## Missing features

* Timeouts
* Connection retries
* trio event loop
* curio event loop

Join the party by bringing your own concurrency library with a PR!

I am looking in particular for implementations over trio and curio.


[pypi]: https://img.shields.io/pypi/pyversions/sockio.svg