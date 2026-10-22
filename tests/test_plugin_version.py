import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_plugin_version_is_3_74_0():
    plugin = json.loads(read(".claude-plugin/plugin.json"))
    assert plugin["version"] == "3.74.0"

    marketplace = json.loads(read(".claude-plugin/marketplace.json"))
    matched = 0
    for entry in marketplace["plugins"]:
        if entry.get("name") == "claudecode-for-me":
            assert entry["version"] == "3.74.0"
            matched += 1
    assert matched >= 1
