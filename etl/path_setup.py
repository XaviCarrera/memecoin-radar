import sys
import os

def setup_project_root():
    """
    Add the project root to the PYTHONPATH if it's not already there.
    """
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.append(project_root)
