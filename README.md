# bulk-scanner

A multi-timeframe Smart Money Concepts (SMC) scanner. It screens a list
of symbols through a pipeline — trend filter → Fair Value Gap (FVG) →
liquidity sweep → break of structure (BOS) → entry confirmation — and
reports the symbols that reach a valid setup.

Phase 1 (this codebase) is a manual CLI tool: one run does one full
scan, prints the results, and exits. A Telegram bot that drives the
same pipeline is scaffolded under `bot/` but not wired up yet.

## Design principles

- **No data source is named anywhere in code, comments, or docs.** The
  backend is accessed only through `data_provider/provider.py`, which is
  entirely config-driven (base URL, endpoint paths, parameter names,
  response field names all come from `config.json`). Swapping data
  sources is a config edit, not a code change.
- **`strategy/engine.py`'s `run_scan()` is pure** — it returns a list of
  results, it never prints. Both `run_cli.py` today and `bot/` later
  call the exact same function.
- **Every strategy module is unit-testable in isolation** with synthetic
  OHLC data. See `tests/`.

## Project layout

```
data_provider/   market data access (HTTP, retry/backoff, pagination)
strategy/        the pipeline: swings, trend, fvg, liquidity, confirmation, engine
bot/             Telegram bot skeleton (formatter.py is used now; telegram_bot.py is not wired up)
run_cli.py       CLI entry point
tests/           one test file per strategy/data_provider/bot module, synthetic data only
config.json      real config, gitignored — you create this
config.example.json   documents every config key with placeholder values
```

## Setup

Requires only the `requests` package — pure Python, no compiled
dependencies, so it installs cleanly on Termux via `pip`.

```
pip install -r requirements.txt
cp config.example.json config.json
```

Edit `config.json` and fill in `base_url` (and `api_key` if your data
source needs one) plus any endpoint/field-name overrides your backend
requires. `config.json` is gitignored — it never gets committed.

A field name in `symbol_field_name` or any `candle_field_map` entry can
be a single name/index or a list of candidates tried in order (e.g.
`["ts", "time", "t"]`) — useful when a backend's field naming isn't
fully pinned down yet. `symbols_extra_params` / `candles_extra_params`
let you send fixed extra query parameters beyond the ones this code
already sets. A raw candle can also be a positional array instead of an
object — use integer indices in `candle_field_map` for that case.

**A note on confidence**: values copied from another project's own
best-effort guess are still a guess, not a verified integration, until
something actually confirms them against a live response. Run
`--check-api` (below) before trusting a new config for real signals.

## Running

```
python run_cli.py
```

With no direction given, it asks interactively:

```
Long? y/n:
```

`y`/`Y` runs the bullish scan, `n`/`N` runs the bearish scan; anything
else re-asks instead of crashing. The direction can still be passed
explicitly (useful for scripting/automation), which skips the prompt:

```
python run_cli.py bullish
python run_cli.py bearish
```

### Diagnosing a config

```
python run_cli.py --check-api
```

Dumps the raw, unparsed JSON from the symbols endpoint and (using
`check_api_symbol`/`check_api_timeframe` from config, or the first
symbol returned live if those are left blank) the candles endpoint, so
endpoint/parameter/field-name mismatches can be diagnosed directly from
real output instead of guessed at.

Each run wraps the scan in `termux-wake-lock` / `termux-wake-unlock`
automatically (a harmless no-op outside Termux) so a long scan across
many symbols isn't killed by the OS while the screen is off.

## Running the tests

```
python -m unittest discover -s tests -v
```

## Pipeline overview

1. **Trend filter** — for each symbol, classify the trend (higher
   highs/higher lows = bullish, lower highs/lower lows = bearish) on
   both a higher and a lower timeframe. Either one aligning with the
   selected direction is enough to pass.
2. **FVG detection** — scan multiple timeframes for a 3-candle Fair
   Value Gap in the selected direction.
3. **Liquidity sweep + BOS** — find the most recent fractal swing before
   the FVG, then look for a candle that sweeps liquidity beyond it,
   followed by a break of structure back through that level.
4. **Entry confirmation** — once price returns into the FVG zone, check
   for a momentum candle or a full engulfing candle. Neither means the
   symbol is reported as "in range" with no signal.

Entry, stop loss, and target (fixed 1:3 risk/reward) are computed as
part of the pipeline itself (`strategy/engine.py`), not in the output
formatting layer, so they stay independently testable.

## Bot phase (not implemented yet)

`bot/telegram_bot.py` contains only the skeleton of what a Telegram bot
integration will look like (start command, direction buttons, a
per-chat scan cooldown) — every method currently raises
`NotImplementedError`. `bot/formatter.py` is already complete and used
by `run_cli.py`, and will be reused unchanged once the bot is wired up.
