import json
import os
import tempfile
import unittest
from unittest.mock import patch

from run_cli import DEFAULTS, load_config, parse_args, resolve_direction, save_config


class TestResolveDirection(unittest.TestCase):
    def test_bullish(self):
        with patch("builtins.input") as mock_input:
            self.assertEqual(resolve_direction(["bullish"]), "bullish")
            mock_input.assert_not_called()

    def test_bearish(self):
        with patch("builtins.input") as mock_input:
            self.assertEqual(resolve_direction(["bearish"]), "bearish")
            mock_input.assert_not_called()

    def test_invalid_direction_exits(self):
        with self.assertRaises(SystemExit):
            resolve_direction(["sideways"])


class TestPromptDirection(unittest.TestCase):
    """No CLI direction given -> interactive y/n prompt."""

    def test_lowercase_y_is_bullish(self):
        with patch("builtins.input", return_value="y"):
            self.assertEqual(resolve_direction([]), "bullish")

    def test_uppercase_y_is_bullish(self):
        with patch("builtins.input", return_value="Y"):
            self.assertEqual(resolve_direction([]), "bullish")

    def test_lowercase_n_is_bearish(self):
        with patch("builtins.input", return_value="n"):
            self.assertEqual(resolve_direction([]), "bearish")

    def test_uppercase_n_is_bearish(self):
        with patch("builtins.input", return_value="N"):
            self.assertEqual(resolve_direction([]), "bearish")

    def test_invalid_input_reprompts_until_valid(self):
        with patch("builtins.input", side_effect=["x", "", "maybe", "y"]) as mock_input:
            self.assertEqual(resolve_direction([]), "bullish")
            self.assertEqual(mock_input.call_count, 4)

    def test_check_api_without_direction_skips_prompt(self):
        with patch("builtins.input") as mock_input:
            self.assertIsNone(resolve_direction(["--check-api"]))
            mock_input.assert_not_called()


class TestCheckApiFlag(unittest.TestCase):
    def test_check_api_makes_direction_optional(self):
        args = parse_args(["--check-api"])
        self.assertTrue(args.check_api)
        self.assertIsNone(args.direction)

    def test_check_api_can_still_be_combined_with_direction(self):
        args = parse_args(["bullish", "--check-api"])
        self.assertTrue(args.check_api)
        self.assertEqual(args.direction, "bullish")


class TestConfigRoundTrip(unittest.TestCase):
    def test_missing_file_is_created_with_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.json")
            config = load_config(path)
            self.assertEqual(config, DEFAULTS)
            self.assertTrue(os.path.exists(path))
            with open(path, "r", encoding="utf-8") as f:
                self.assertEqual(json.load(f), DEFAULTS)

    def test_existing_file_overrides_merge_over_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.json")
            save_config({"base_url": "http://example.invalid", "max_workers": 5}, path)
            config = load_config(path)
            self.assertEqual(config["base_url"], "http://example.invalid")
            self.assertEqual(config["max_workers"], 5)
            self.assertEqual(config["top_symbols_limit"], DEFAULTS["top_symbols_limit"])


if __name__ == "__main__":
    unittest.main()
