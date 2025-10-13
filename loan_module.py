# loan_module.py — adapter shim for tests/monkeypatch
from modules.loan_module import *  # re-export everything

# expose get_project_paths at top-level so tests can monkeypatch it
from modules.utils import get_project_paths as _base_get_project_paths
def get_project_paths(root_hint=None):
    return _base_get_project_paths(root_hint)
