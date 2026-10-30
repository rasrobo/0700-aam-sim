#!/usr/bin/env python3
"""
Simulate an operator interacting with the 0700-aam-sim terminal dashboard:
1. Hit pads across rows and banks
2. Turn Q-Link knobs
3. Touch slider
4. Inject gestures
5. Toggle transport
"""
import pty
import os
import time
import subprocess
import select
from pathlib import Path

def run_demo():
    master, slave = pty.openpty()
    repo_root = Path(__file__).resolve().parent.parent
    bin_path = repo_root / "build" / "0700-aam-sim"
    proc = subprocess.Popen(
        [str(bin_path), "--interactive"],
        stdin=slave,
        stdout=slave,
        stderr=slave,
        close_fds=True
    )
    os.close(slave)

    # Let the dashboard boot
    time.sleep(1.5)

    def send_keys(keys, delay=0.3):
        for k in keys:
            os.write(master, k.encode("utf-8"))
            time.sleep(delay)

    # 1. Switch banks and tap pads
    send_keys(["z", "x", "c", "v"], 0.25) # Row 1
    send_keys(["a", "s", "d", "f"], 0.25) # Row 2
    send_keys(["q", "w", "e", "r"], 0.25) # Row 3
    send_keys(["1", "2", "3", "4"], 0.25) # Row 4

    time.sleep(0.5)
    send_keys(["B"], 0.3) # Switch to Bank B
    send_keys(["q", "w", "e", "r"], 0.25)
    send_keys(["C"], 0.3) # Switch to Bank C
    send_keys(["a", "s", "d", "f"], 0.25)
    send_keys(["A"], 0.3) # Back to Bank A

    # 2. Adjust Q-Link knobs
    send_keys(["7", "]", "]", "]", "]"], 0.2) # P1 up
    send_keys(["8", "]", "]", "]", "]"], 0.2) # P2 up
    send_keys(["9", "]", "]", "]", "]"], 0.2) # P3 up
    send_keys(["0", "]", "]", "]", "]"], 0.2) # P4 up

    # 3. Touch slider and jog wheel
    send_keys(["t", "t", "t", "t"], 0.3)
    send_keys([">", ">", ">", ">", "<", "<"], 0.2) # Jog wheel
    send_keys(["\n"], 0.3) # Jog push

    # 4. Inject synthetic AI camera gestures
    send_keys(["g", "g", "g"], 0.6)

    # 5. Transport toggles
    send_keys(["R"], 0.4) # Record
    send_keys([" "], 0.4) # Play
    time.sleep(1.0)
    send_keys(["S"], 0.4) # Stop
    time.sleep(0.5)

    # Clean exit
    os.write(master, b"\x03")
    proc.terminate()
    proc.wait()
    os.close(master)

if __name__ == "__main__":
    run_demo()
