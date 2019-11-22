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
* python 2 compatible blocking API (for those pour souls stuck with python 2)


## Installation

From within your favourite python environment:

```console
pip install sockio
```

## Usage

*asyncio*

```python
import asyncio
from sockio.aio import TCP

async def main():
    sock = TCP('acme.example.com', 5000)
    # Assuming a SCPI complient on the other end we can ask for:
    reply = await sock.write_readline(b'*IDN?\n')
    print(reply)

asyncio.run(main())
```

*classic*

```python
from sockio.sio import TCP

sock = TCP('acme.example.com', 5000)
reply = sock.write_readline(b'*IDN?\n')
print(reply)
```

*concurrent.futures*

```python
from sockio.sio import TCP

sock = TCP('acme.example.com', 5000, resolve_futures=False)
reply = sock.write_readline(b'*IDN?\n').result()
print(reply)
```

*python 2 compatibility*

```python
from sockio.py2 import TCP

sock = TCP('acme.example.com', 5000, resolve_futures=False)
reply = sock.write_readline(b'*IDN?\n').result()
print(reply)
```

## Features

The main goal of a sockio TCP object is to facilitate communication
with instruments which listen on a TCP socket.

The most frequent cases include instruments which expect a REQ/REP
semantics with ASCII protocols like SCPI. In these cases most commands
translate in small packets being exchanged between the host and the
instrument. Care has been taken in this library to make sure we reduce
latency as much as possible. This translates into the following defaults
when creating a TCP object:

* TCP no delay is active. Can be disabled with `TCP(..., no_delay=False)`.
  This prevents the kernel from applying
  [Nagle's algorithm](https://en.wikipedia.org/wiki/Nagle%27s_algorithm)
* TCP ToS is set to LOWDELAY. This effectively prioritizes our packets
  if favor of other concurrent communications. Can be disabled with
  `TCP(tos=IPTOS_NORMAL)`


### REQ-REP semantics

Many instruments out there have a Request-Reply protocol. A sockio TCP
provides `write_read` family of methods which simplify communication with
these instruments. These methods are atomic which means different tasks or
threads can safely work with the same socket object (although I would
question myself why would I be doing that in my library/application).

### Auto-reconnection

```python
sock = TCP('acme.example.com', 5000)
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
A sockio TCP can be customized with a different EOL character. Example:

```python
sock = TCP('acme.example.com', 5000, eol=b'\r')
```

The EOL character can be overwritten in any of the `readline` methods. Example:
```python
await sock.write_readline(b'*IDN?\n', eol=b'\r')
```

### Connection event callbacks

You can be notified on `connection_made`, `connection_lost` and `eof_received` events
by registering callbacks on the sockio TCP constructor

This is particularly useful if, for example, you want a specific procedure to be
executed every time the socket is reconnected to make sure your configuration is
right. Example:

```python
async def connected():
    await sock.write(b'ACQU:TRIGGER HARDWARE\n')
    await sock.write(b'DISPLAY OFF\n')

sock = TCP('acme.example.com', 5000, on_connection_made=connected)
```

(see examples/req-rep/client.py)

Connection event callbacks are **not** available in *python 2 compatibility module*.

### Streams

sockio TCPs are asynchronous iterable objects. This means that line streaming
is as easy as:

```python
sock = TCP('acme.example.com', 5000, eol=b'\r')

async for line in sock:
    print(line)
```

Streams are **not** available in *python 2 compatibility module*. Let me know
if you need them by writing an issue. Also feel free to make a PR!

## Missing features

* Timeouts
* Connection retries
* trio event loop
* curio event loop

Join the party by bringing your own concurrency library with a PR!

I am looking in particular for implementations over trio and curio.


[pypi]: https://img.shields.io/pypi/pyversions/sockio.svg