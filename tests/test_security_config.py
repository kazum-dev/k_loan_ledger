import os
import subprocess
import sys


def test_production_requires_secret_key():
    env = os.environ.copy()

    env["APP_ENV"] = "production"
    env.pop("SECRET_KEY", None)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import app",
        ],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert (
        "SECRET_KEY must be set in production."
        in result.stderr
    )