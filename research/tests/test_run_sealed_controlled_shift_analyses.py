from __future__ import annotations

import tempfile
from pathlib import Path

from run_sealed_controlled_shift_analyses import require_absent, run_suppressed, seal


def main() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        output = root / "output.json"
        log = root / "suppressed.log"
        command = (
            "/bin/sh",
            "-c",
            f"printf '{{}}\\n' > '{output}'; printf 'private-value\\n'",
        )
        record = run_suppressed(command, cwd=root, log_path=log)
        assert record["returncode"] == 0
        assert "private-value" in log.read_text(encoding="utf-8")
        artifact = seal(output)
        assert artifact["mode"] == "0o444"
        try:
            require_absent(output)
        except RuntimeError:
            print("PASS sealed runner rejects overwrite")
        else:
            raise AssertionError("sealed overwrite check passed")
        failing_log = root / "failure.log"
        try:
            run_suppressed(("/bin/sh", "-c", "exit 7"), cwd=root, log_path=failing_log)
        except RuntimeError:
            assert oct(failing_log.stat().st_mode & 0o777) == "0o400"
            print("PASS sealed runner records suppressed failure")
        else:
            raise AssertionError("failed subprocess passed")


if __name__ == "__main__":
    main()
