import os
import yaml
from pathlib import Path

CONFIG_DIR = Path.home() / ".jobs"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

DEFAULT_CONFIG = {
    "titles": [
        "VP of Product",
        "VP Product",
        "Head of Product",
        "Director of Product",
        "Chief Product Officer",
    ],
    "sources": ["ashby", "lever", "greenhouse"],
    # Optional: add your SerpAPI key here for more reliable search results.
    # Free tier gives ~100 searches/month. Sign up at https://serpapi.com
    "serpapi_key": None,
}


def load_config() -> dict:
    """Load config from ~/.jobs/config.yaml, falling back to defaults."""
    if not CONFIG_FILE.exists():
        return DEFAULT_CONFIG.copy()
    with open(CONFIG_FILE) as f:
        user_config = yaml.safe_load(f) or {}
    config = DEFAULT_CONFIG.copy()
    config.update(user_config)
    return config


def init_config() -> Path:
    """Create the config directory and default config file if they don't exist."""
    CONFIG_DIR.mkdir(exist_ok=True)
    if not CONFIG_FILE.exists():
        with open(CONFIG_FILE, "w") as f:
            yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False, sort_keys=False)
    return CONFIG_FILE


def open_config_in_editor():
    """Open the config file in the user's $EDITOR."""
    init_config()
    editor = os.environ.get("EDITOR", "nano")
    os.system(f'{editor} "{CONFIG_FILE}"')
