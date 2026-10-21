from gevent import monkey

monkey.patch_all(sys=True)

# pytest plugins can import SSL, so patch before loading pytest.
import pytest  # ruff: ignore[module-import-not-at-top-of-file]

raise SystemExit(pytest.main())
