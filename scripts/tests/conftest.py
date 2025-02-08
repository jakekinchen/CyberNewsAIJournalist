import os
import sys

# Add the scripts directory to the Python path
scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts'))
sys.path.insert(0, scripts_dir) 