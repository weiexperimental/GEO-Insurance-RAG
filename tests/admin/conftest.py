# Tests rely on PYTHONPATH=admin/backend being set when running pytest.
# No sys.path manipulation needed.

# The root conftest mocks opensearchpy for server tests that lack the library.
# Admin tests use the real opensearchpy, so restore it if it's installed.
import sys

_mocked_keys = [k for k in list(sys.modules) if k == "opensearchpy" or k.startswith("opensearchpy.")]
for _k in _mocked_keys:
    del sys.modules[_k]

try:
    import opensearchpy  # noqa: F401 — triggers real import into sys.modules
except ImportError:
    pass  # Not installed; leave removed (imports will fail)
