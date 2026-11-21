"""Exercise the actual interactive dashboard in a POSIX pseudo-terminal."""

import os
import sys

import pytest


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX pseudo-terminal and signals")
def test_dashboard_resize_and_interrupt(tmp_path):
    import fcntl
    import pty
    import select
    import signal
    import struct
    import subprocess
    import termios
    import time

    master, slave = pty.openpty()
    env = dict(os.environ, XDG_CONFIG_HOME=str(tmp_path))
    process = subprocess.Popen(
        [sys.executable, "-m", "forgekit", "dashboard", "--refresh", "0.5"],
        stdin=slave,
        stdout=slave,
        stderr=slave,
        env=env,
        start_new_session=True,
    )
    os.close(slave)
    output = bytearray()
    try:
        deadline = time.monotonic() + 15
        while b"Starting dashboard" not in output and time.monotonic() < deadline:
            if select.select([master], [], [], 0.25)[0]:
                output.extend(os.read(master, 65536))
            if process.poll() is not None:
                break
        assert b"Starting dashboard" in output
        fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 72, 0, 0))
        os.killpg(process.pid, signal.SIGWINCH)
        time.sleep(0.25)
        os.killpg(process.pid, signal.SIGINT)
        assert process.wait(timeout=10) == 0
        while select.select([master], [], [], 0)[0]:
            try:
                output.extend(os.read(master, 65536))
            except OSError:
                break
        assert b"Dashboard exited." in output
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        os.close(master)
