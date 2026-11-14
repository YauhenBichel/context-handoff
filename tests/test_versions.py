import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import context_handoff  # noqa: E402


class VersionsAgree(unittest.TestCase):
    """The Python package and the Claude Code plugin are released together, from one tag."""

    def test_plugin_json_matches_package(self):
        plugin = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
        self.assertEqual(plugin["version"], context_handoff.__version__)

    def test_marketplace_entry_does_not_pin_another_version(self):
        market = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
        for entry in market["plugins"]:
            self.assertEqual(entry.get("version", context_handoff.__version__), context_handoff.__version__)

    def test_changelog_has_this_version(self):
        self.assertIn(f"## {context_handoff.__version__} ", (ROOT / "CHANGELOG.md").read_text())

    def test_pyproject_reads_version_from_package(self):
        text = (ROOT / "pyproject.toml").read_text()
        self.assertIn('dynamic = ["version"]', text)
        self.assertIn('version = { attr = "context_handoff.__version__" }', text)


if __name__ == "__main__":
    unittest.main()
