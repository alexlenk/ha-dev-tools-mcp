"""Entry point for running the MCP server as a module.

This module enables running the server via:
    python -m ha_config_manager

It handles:
- Importing and calling main() from server.py
- Graceful shutdown on KeyboardInterrupt
- Proper async execution with asyncio.run()
"""

import asyncio
import sys
import logging
from .server import main

# Configure logging for the entry point
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def run():
    """Run the MCP server with proper error handling."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Server failed to start: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run()
