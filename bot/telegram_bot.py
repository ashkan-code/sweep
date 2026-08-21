"""Skeleton for the future Telegram bot integration. NOT wired up yet:
this module does not import a Telegram bot library (not yet a
dependency) and is not called from run_cli.py or anywhere else.

Future intent: a start command that offers "bullish"/"bearish" buttons,
a per-chat cooldown between user-triggered scans, and wiring the chosen
direction into strategy.engine.run_scan() + bot.formatter for the reply.
"""

DEFAULT_COOLDOWN_SECONDS = 180  # 3 minutes between user-triggered scans


class ScanCooldown:
    """Will track the last scan time per chat/user id so repeated button
    presses within the cooldown window are rejected. Kept separate from
    TelegramBot so it can eventually be unit tested on its own."""

    def __init__(self, cooldown_seconds=DEFAULT_COOLDOWN_SECONDS):
        self._cooldown_seconds = cooldown_seconds

    def is_ready(self, chat_id, now=None):
        raise NotImplementedError("wired up once the bot is implemented")

    def mark_scanned(self, chat_id, now=None):
        raise NotImplementedError("wired up once the bot is implemented")


class TelegramBot:
    """Future home of the bot application, the start-command handler
    (bullish/bearish buttons), and callback wiring to
    strategy.engine.run_scan() + bot.formatter. Not constructed anywhere
    in phase 1; run_cli.py remains the only entry point."""

    def __init__(self, config):
        self._config = config
        self._cooldown = ScanCooldown(config.get("bot_cooldown_seconds", DEFAULT_COOLDOWN_SECONDS))

    def handle_start(self, chat_id):
        """Future: send the bullish/bearish button prompt."""
        raise NotImplementedError

    def handle_direction_choice(self, chat_id, direction):
        """Future: enforce cooldown, call strategy.engine.run_scan(direction, ...),
        format with bot.formatter, send the message(s) back to chat_id."""
        raise NotImplementedError
