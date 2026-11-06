"""Usage parsing of Claude Code stream-json output (no Docker)."""
import json

from p2o.harness import StreamUsage
from p2o.worker import parse_stream


def _ev(event):
    return json.dumps({"type": "stream_event", "event": event})


ZERO = {"input_tokens": 0, "output_tokens": 0}
LINES = [
    json.dumps({"type": "system", "subtype": "init", "model": "m"}),
    _ev({"type": "message_start", "message": {"id": "a", "usage": {"input_tokens": 100, "output_tokens": 1}}}),
    _ev({"type": "content_block_delta", "delta": {"text": "x"}}),
    json.dumps({"type": "assistant", "message": {"id": "a", "usage": ZERO}}),
    _ev({"type": "message_delta", "usage": {"output_tokens": 30, "cache_read_input_tokens": 50}}),
    _ev({"type": "message_start", "message": {"id": "b", "usage": ZERO}}),
    _ev({"type": "message_delta", "usage": {"input_tokens": 200, "output_tokens": 10}}),
]


def test_stream_events_used_when_no_result():
    u, result, cap = parse_stream("\n".join(LINES))
    assert result is None and cap is None
    assert (u.tokens_in, u.tokens_out, u.tokens_cached) == (300, 40, 50)


def test_result_usage_preferred_when_nonzero():
    res = json.dumps({"type": "result", "subtype": "success",
                      "usage": {"input_tokens": 7, "output_tokens": 8, "cache_read_input_tokens": 9}})
    u, result, _ = parse_stream("\n".join(LINES + [res]))
    assert result["subtype"] == "success"
    assert (u.tokens_in, u.tokens_out, u.tokens_cached) == (7, 8, 9)


def test_zero_result_usage_falls_back_to_stream():
    res = json.dumps({"type": "result", "subtype": "error_max_turns", "usage": ZERO})
    u, _, _ = parse_stream("\n".join(LINES + [res]))
    assert u.tokens_out == 40


def test_cap_marker_and_meter_total():
    m = StreamUsage()
    kept = [m.feed(line) for line in LINES]
    assert kept.count("message_start") == 2 and kept.count("message_delta") == 2
    assert m.total() == 100 + 30 + 50 + 200 + 10
    _, _, cap = parse_stream("\n".join(LINES + [json.dumps({"type": "p2o_cap", "reason": "cap_tokens"})]))
    assert cap == "cap_tokens"
