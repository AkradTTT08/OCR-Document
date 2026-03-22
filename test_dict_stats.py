import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

import logging

# Configure logging to stdout
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

from dictionary_manager import get_dictionary_stats

def test_stats():
    print("Fetching Dictionary Stats...")
    stats = get_dictionary_stats()
    print("-" * 30)
    for key, value in stats.items():
        print(f"{key}: {value}")
    print("-" * 30)

if __name__ == "__main__":
    test_stats()
