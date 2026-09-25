"""CLI: python -m src.dashboard"""

from __future__ import annotations

import argparse
import logging

from src.config import get_settings
from src.dashboard.server import serve_dashboard


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="rETH basis research check-in dashboard")
    parser.add_argument("--host", default=None, help="Bind host (default DASHBOARD_HOST)")
    parser.add_argument("--port", type=int, default=None, help="Bind port (default DASHBOARD_PORT)")
    args = parser.parse_args(argv)

    get_settings.cache_clear()
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    serve_dashboard(settings=settings, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
