import json
from threading import Thread
from unittest import TestCase
from urllib.error import HTTPError
from urllib.request import urlopen

from serve import FIXTURE, Handler, ThreadingHTTPServer, run


class HttpTest(TestCase):
    def test_routes_and_validation(self):
        with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                with urlopen(base, timeout=3) as response:
                    self.assertIn(b'name="viewport"', response.read())
                with urlopen(base + "/api/replay", timeout=3) as response:
                    self.assertEqual(json.load(response), run(FIXTURE, {}))
                for query in ("unknown=1", "shares=NaN", "test=1&test=2"):
                    with self.assertRaises(HTTPError) as failure:
                        urlopen(base + "/api/replay?" + query, timeout=3)
                    with failure.exception as response:
                        self.assertEqual(response.code, 400)
                with self.assertRaises(HTTPError) as failure:
                    urlopen(base + "/not-a-route", timeout=3)
                failure.exception.close()
                self.assertEqual(failure.exception.code, 404)
            finally:
                server.shutdown()
                thread.join(timeout=3)

class ReplayTest(TestCase):
    def test_full_fill_then_remaining_depth_only(self):
        result = run(FIXTURE, {})
        self.assertEqual(result["rows"][0][3:6], ["Filled", "10.00 / 10.00", "0.5300"])
        self.assertEqual(result["rows"][1][3:6], ["Partial", "2.00 / 10.00", "0.5400"])
        self.assertEqual(dict(result["metrics"])["Shares filled"], "39.00")
        self.assertEqual(dict(result["metrics"])["Assumed fee ($)"], "0.0419")

    def test_no_future_book_at_order_arrival(self):
        result = run(FIXTURE, {"latency": "0"})
        self.assertEqual(result["rows"][2][-1], "No earlier snapshot for this outcome")
        self.assertEqual(result["rows"][6][-1], "Snapshot is stale at order arrival")

    def test_price_cap_and_window_are_enforced(self):
        rows = run(FIXTURE, {"limit": "0.50"})["rows"]
        self.assertEqual(rows[0][3], "No fill")
        self.assertEqual(rows[2][4], "3.00 / 10.00")
        self.assertEqual(rows[-1][-1], "Order arrives after the replay window")

    def test_reject_invalid_numbers(self):
        for value in ("0", "1", "NaN", "1e-1"):
            with self.assertRaises(ValueError):
                run(FIXTURE, {"limit": value})
