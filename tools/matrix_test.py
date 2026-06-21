#!/usr/bin/env python3
"""AKII matrix bring-up tester.

Reads ZMK USB-serial debug logs (CONFIG_ZMK_USB_LOGGING=y) and checks off
every matrix position as you press it. Run, then press every key once;
green = seen, dim = not yet. Ctrl+C prints a summary of silent positions.

Usage: python3 matrix_test.py [/dev/tty.usbmodemXXXX]
"""

import glob
import os
import re
import select
import sys
import termios

# (row, col) -> label, in physical layout order (matches akii.overlay transform
# and akii.keymap). RC(0,18) is the encoder push switch via kscan-direct.
LAYOUT = [
    [((0, c), n) for c, n in enumerate(
        "` 1 2 3 4 5 6 7 8 9 0 - = BSPC FN K= K/ K*".split())],
    [((1, c), n) for c, n in enumerate(
        "TAB Q W E R T Y U I O P [ ] \\ K7 K8 K9 K-".split())],
    [((2, c), n) for c, n in zip(list(range(13)) + [14, 15, 16, 17],
        "CAPS A S D F G H J K L ; ' RET K4 K5 K6 K+".split())],
    [((3, c), n) for c, n in zip(list(range(11)) + [12, 14, 15, 16],
        "LSHFT Z X C V B N M , . / RSHFT K1 K2 K3".split())]
    + [((4, 17), "KENT")],
    [((4, c), n) for c, n in zip([0, 1, 2, 5, 9, 10, 11, 12, 13, 15, 16],
        "LCTRL LALT LGUI SPACE RGUI LEFT DOWN UP RIGHT K0 K.".split())],
    [((0, 18), "ENC-CLICK")],
]
EXPECTED = {rc: name for row in LAYOUT for rc, name in row}

EVENT_RE = re.compile(
    r"Row:\s*(\d+),\s*col(?:umn)?:\s*(\d+),.*pressed:\s*(true|false)", re.I)
ERROR_RE = re.compile(r"<err>|i2c.*(?:err|fail|nack)|mcp23", re.I)

GREEN, DIM, RED, RESET = "\033[32;1m", "\033[2m", "\033[31;1m", "\033[0m"


def find_port():
    if len(sys.argv) > 1:
        return sys.argv[1]
    candidates = sorted(glob.glob("/dev/tty.usbmodem*"))
    if not candidates:
        sys.exit("No /dev/tty.usbmodem* device found. Is the AKII plugged in "
                 "and running the USB-logging firmware?")
    if len(candidates) > 1:
        print("Multiple serial devices found, pass one explicitly:")
        for c in candidates:
            print("  ", c)
        sys.exit(1)
    return candidates[0]


def render(seen, errors, last_event):
    print("\033[2J\033[H", end="")
    print(f"AKII matrix test -- press every key. "
          f"{len(seen)}/{len(EXPECTED)} verified, Ctrl+C to finish.\n")
    for row in LAYOUT:
        cells = []
        for rc, name in row:
            color = GREEN if rc in seen else DIM
            cells.append(f"{color}{name}{RESET}")
        print("  " + "  ".join(cells))
    if last_event:
        print(f"\nlast event: {last_event}")
    if errors:
        print(f"\n{RED}driver errors seen:{RESET}")
        for line in errors[-5:]:
            print("  " + line)


def main():
    port = find_port()
    fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    attrs = termios.tcgetattr(fd)
    attrs[0] = attrs[1] = attrs[3] = 0          # iflag, oflag, lflag: raw
    attrs[2] |= termios.CLOCAL | termios.CREAD  # cflag: ignore carrier
    termios.tcsetattr(fd, termios.TCSANOW, attrs)

    seen, errors, unexpected = set(), [], set()
    buf, last_event = b"", ""
    render(seen, errors, last_event)
    try:
        while True:
            r, _, _ = select.select([fd], [], [], 0.5)
            if not r:
                continue
            try:
                chunk = os.read(fd, 4096)
            except BlockingIOError:
                continue
            if not chunk:
                continue
            buf += chunk
            *lines, buf = buf.split(b"\n")
            dirty = False
            for raw in lines:
                line = raw.decode(errors="replace").strip()
                m = EVENT_RE.search(line)
                if m:
                    rc = (int(m.group(1)), int(m.group(2)))
                    pressed = m.group(3).lower() == "true"
                    state = "press" if pressed else "release"
                    last_event = f"row {rc[0]} col {rc[1]} {state}"
                    if pressed:
                        if rc in EXPECTED:
                            seen.add(rc)
                        else:
                            unexpected.add(rc)
                            last_event += "  (NOT IN LAYOUT!)"
                    dirty = True
                elif ERROR_RE.search(line):
                    errors.append(line)
                    dirty = True
            if dirty:
                render(seen, errors, last_event)
    except KeyboardInterrupt:
        pass
    finally:
        os.close(fd)

    print("\n--- summary ---")
    missing = {rc: n for rc, n in EXPECTED.items() if rc not in seen}
    print(f"verified: {len(seen)}/{len(EXPECTED)}")
    if missing:
        print(f"{RED}silent positions (check solder joints):{RESET}")
        for (row, col), name in sorted(missing.items()):
            print(f"  row {row:>2} col {col:>2}  {name}")
    else:
        print(f"{GREEN}all positions verified!{RESET}")
    if unexpected:
        print(f"{RED}unexpected positions (shorts / wrong wiring?):{RESET}")
        for row, col in sorted(unexpected):
            print(f"  row {row:>2} col {col:>2}")


if __name__ == "__main__":
    main()
