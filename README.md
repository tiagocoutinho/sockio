# sockio

A concurrency agnostic socket library on python.

So far implemented REQ-REP semantics with auto-reconnection facilites.

Implementations for:

* classic blocking API
* future based API
* asyncio

Join the party by bringing your own concurrency library with a PR!

I am looking in particular for implementations over trio and curio.

## Missing features

* Timeouts
* Connection retries
* trio event loop
* curio event loop
* Stream semantics

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




