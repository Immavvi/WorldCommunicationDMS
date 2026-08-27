"""Launch one WCDMS development service detached from the invoking terminal."""

import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    cwd, log_path, *command = sys.argv[1:]
    environment = os.environ.copy()
    if command[0].startswith("VITE_API_BASE_URL="):
        key, value = command.pop(0).split("=", 1)
        environment[key] = value
    with Path(log_path).open("ab", buffering=0) as log:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    print(process.pid)


if __name__ == "__main__":
    main()
