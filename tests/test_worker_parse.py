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


def _result(turn_usage, model_usage):
    return json.dumps({"type": "result", "subtype": "success", "usage": turn_usage,
                       "modelUsage": {"m": model_usage}})


def test_without_stream_events_last_result_model_usage_is_used_not_turn_usage():
    # background-task turns emit extra result events; result.usage is per turn, modelUsage cumulative
    r1 = _result({"input_tokens": 5, "output_tokens": 5},
                 {"inputTokens": 1000, "outputTokens": 400, "cacheReadInputTokens": 9000})
    r2 = _result({"input_tokens": 1, "output_tokens": 1},
                 {"inputTokens": 1100, "outputTokens": 420, "cacheReadInputTokens": 9500,
                  "cacheCreationInputTokens": 10})
    no_stream = [line for line in LINES if '"stream_event"' not in line]
    u, result, _ = parse_stream("\n".join(no_stream + [r1, r2]))
    assert result["usage"]["input_tokens"] == 1
    assert (u.tokens_in, u.tokens_out, u.tokens_cached) == (1110, 420, 9500)


def test_stream_events_preferred_over_model_usage():
    # modelUsage double-counts input via OpenRouter; stream sum is exact and covers post-kill turns
    r1 = _result(ZERO, {"inputTokens": 999, "outputTokens": 1, "cacheReadInputTokens": 0})
    u, _, _ = parse_stream("\n".join(LINES + [r1]))
    assert (u.tokens_in, u.tokens_out, u.tokens_cached) == (300, 40, 50)


def test_meter_usd_matches_pricing():
    from p2o.config import Prices
    from p2o.pricing import usd
    m = StreamUsage()
    for line in LINES:
        m.feed(line)
    p = Prices(input=0.15, cached_input=0.03, output=0.5)
    u, _, _ = parse_stream("\n".join(LINES))
    assert abs(m.usd(p.model_dump()) - usd(u, p)) < 1e-12


def test_cap_marker_and_meter_total():
    m = StreamUsage()
    kept = [m.feed(line) for line in LINES]
    assert kept.count("message_start") == 2 and kept.count("message_delta") == 2
    assert m.total() == 100 + 30 + 50 + 200 + 10
    _, _, cap = parse_stream("\n".join(LINES + [json.dumps({"type": "p2o_cap", "reason": "cap_tokens"})]))
    assert cap == "cap_tokens"
