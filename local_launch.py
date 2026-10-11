"""Local launcher: Gemini configuration and project-local runtime files."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

root = Path(__file__).resolve().parent
os.chdir(root)
load_dotenv(root / ".env")
for name, path in {
    "TRADINGAGENTS_RESULTS_DIR": root / "reports",
    "TRADINGAGENTS_CACHE_DIR": root / "local-data" / "cache",
    "TRADINGAGENTS_MEMORY_LOG_PATH": root / "local-data" / "memory" / "trading_memory.md",
}.items():
    os.environ.setdefault(name, str(path))

if not any(arg in ("--help", "--version") for arg in sys.argv[1:]):
    if not os.environ.get("GOOGLE_API_KEY", "").strip():
        sys.exit("请先在项目 .env 文件的 GOOGLE_API_KEY= 后填写 Gemini 密钥，再启动。")

import cli.prefs

cli.prefs._PREFS_PATH = root / "local-data" / "cli_prefs.json"

from cli.main import app

if __name__ == "__main__":
    app()
