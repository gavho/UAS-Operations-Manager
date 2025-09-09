#!/usr/bin/env python3
"""
Launcher script for the Flight Operations Management application.
This script ensures proper Python path setup before running the application.
"""
import os
import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

def main():
    # Import and run the application
    try:
        # The main application is in main.py, not app.app
        import subprocess
        import sys
        project_root = str(Path(__file__).parent.absolute())
        result = subprocess.run([sys.executable, 'main.py'], cwd=project_root)
        sys.exit(result.returncode)
    except Exception as e:
        logger.critical("Failed to start application", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
