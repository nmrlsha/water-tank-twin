import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import history_client as hc

ROWS = [{"timestamp": f"2026-11-02T08:00:{i:02d}Z", "level_pct": 40.0 + i, "predicted_level_pct": None if i < 2 else 50.0,
         "alarm": "overflow_risk" if i == 4 else "none"} for i in range(6)]
AGG = [{"minute": "2026-11-02T08:00", "mean_level_pct": 42.512, "max_inflow_lpm": 8.0, "alarm_count": 0, "samples": 60}]


def start_server(routes):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?")[0]
            code, body = routes.get(path, (404, {"detail": "nope"}))
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


@pytest.fixture
def api():
    server, url = start_server({"/history": (200, ROWS), "/aggregates": (200, AGG)})
    yield url
    server.shutdown()


def test_extract_rows_accepts_list_or_dict():
    assert hc.extract_rows(ROWS) == ROWS
    assert hc.extract_rows({"rows": ROWS}) == ROWS
    assert hc.extract_rows({"data": ROWS, "count": 6}) == ROWS
    assert hc.extract_rows({"points": ROWS, "count": 6}) == ROWS            # the real API's key
    assert hc.extract_rows({"asset_id": "tank_01", "stuff": ROWS}) == ROWS  # unknown key holding rows
    assert hc.extract_rows("junk") == [] and hc.extract_rows({"x": 1}) == []


def test_real_api_answer_shape():
    real = {"asset_id": "tank_01", "minutes": 5, "step": 30, "count": 1, "points": [
        {"id": 10050, "asset_id": "tank_01", "timestamp": "2026-11-13T04:07:32Z",
         "received_at": "2026-11-13T04:07:32.869224Z", "level_pct": 55.72, "inflow_lpm": 9.72,
         "outflow_lpm": 0.0, "pump_on": False, "predicted_level_pct": 66.19, "alarm": "none"}]}
    s = hc.summarize(hc.extract_rows(real))
    assert s["levels"] == [55.72] and s["alarm_readings"] == 0


def test_summarize():
    s = hc.summarize(ROWS)
    assert s["levels"] == [40, 41, 42, 43, 44, 45] and s["alarm_readings"] == 1
    assert s["first_timestamp"].endswith("00Z") and s["last_timestamp"].endswith("05Z")
    assert hc.summarize([{"level_pct": None}, {"level_pct": "x"}])["levels"] == []


def test_aggregate_lines_rounds_floats():
    assert "mean_level_pct=42.5" in hc.aggregate_lines(AGG)[0]


def test_points_step():
    assert hc.points_step(5) == 1 and hc.points_step(60) == 12


def test_fetch_ok(api):
    r = hc.HistoryClient(api).fetch(5)
    assert r["ok"] and len(r["levels"]) == 6 and r["error"] is None
    assert "samples=60" in r["aggregate_lines"][0]


def test_fetch_survives_missing_aggregates():
    server, url = start_server({"/history": (200, {"rows": ROWS})})
    r = hc.HistoryClient(url).fetch(5)
    server.shutdown()
    assert r["ok"] and r["aggregate_lines"] == ["aggregates unavailable"]


@pytest.mark.parametrize("code,text", [(503, "database not created"), (404, "no data stored")])
def test_http_errors_are_messages_not_crashes(code, text):
    server, url = start_server({"/history": (code, {"detail": "x"})})
    r = hc.HistoryClient(url).fetch(5)
    server.shutdown()
    assert not r["ok"] and text in r["error"]


def test_empty_history():
    server, url = start_server({"/history": (200, [])})
    r = hc.HistoryClient(url).fetch(5)
    server.shutdown()
    assert not r["ok"] and "no stored readings" in r["error"]


def test_api_down_is_a_message_not_a_crash():
    r = hc.HistoryClient("http://127.0.0.1:1", timeout_s=1).fetch(5)
    assert not r["ok"] and "not reachable" in r["error"]


def test_background_request_and_poll(api):
    c = hc.HistoryClient(api)
    assert c.poll() is None
    assert c.request(5) is True
    deadline = time.time() + 3
    result = None
    while result is None and time.time() < deadline:
        result = c.poll()
        time.sleep(0.02)
    assert result and result["ok"] and not c.busy