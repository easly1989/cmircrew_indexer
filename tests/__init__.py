# Test suite setup for MirCrew Indexer
# This file enables unittest discover to properly locate and run all tests

import os
import sys

# Add the src directory to Python path so imports work correctly
project_root = os.path.dirname(os.path.dirname(__file__))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)