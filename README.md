# Polymarket BTC Replay

Replay BTC outcome signals against timestamped YES/NO books. See which simulated orders fill and why the others do not.

## Run locally

Python 3.11+; no dependencies, service accounts, or network calls are required.

~~~sh
python3 serve.py
~~~

Open http://127.0.0.1:8000. Use `--port 8001` if port 8000 is busy.

Run the defaults to see a full fill followed by a partial fill on the same snapshot. Lower the price cap to `0.50` to see the higher-priced asks excluded.

## How it works

The simulated IOC order arrives after the configured delay and uses only the newest fixture book at or before arrival. It walks eligible asks in price order, tracks consumed levels within a snapshot, rejects stale quotes and cancels any unfilled remainder. The journal shows the simulated fill quantity and size-weighted price.

The tape is synthetic; it is not an export of real signals, trading records or returns. The fee is an explicit fixed scenario assumption, not a claim about Polymarket's fee schedule. The replay does not model queue position, order acknowledgments, settlement or production trading. A new snapshot replaces the assumed book.

## Check the result

~~~sh
python3 -B -m unittest -v
curl 'http://127.0.0.1:8000/api/replay?shares=10&latency=500&limit=0.50&fee=20'
~~~

`fixture.json` is the input, `demo.py` calculates the result, and `serve.py` serves the browser UI and the same result as JSON.
