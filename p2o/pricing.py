"""Token usage -> USD from the config's price table. # STATUS: implemented

Never use Claude Code's total_cost_usd with a non-Anthropic endpoint: it is priced at Anthropic rates.
`tokens_in` here means uncached input tokens.
"""
from .config import Prices
from .types import Usage


def usd(usage: Usage, p: Prices) -> float:
    return (usage.tokens_in * p.input + usage.tokens_cached * p.cached_input
            + usage.tokens_out * p.output) / 1_000_000
