"""Run the capture agent locally: python -m agent [--surfaces teams_desktop,gmail_web].

Prints counts only. Typed text is never printed, logged or written anywhere.
"""

import argparse
import time

from agent.buffer import RingBuffer
from agent.capture import Capture
from agent.config import ALL_SURFACES, DEFAULT_ALLOWED_SURFACES

STATUS_INTERVAL_S = 5


def main() -> None:
    parser = argparse.ArgumentParser(description="whoknows capture agent")
    parser.add_argument(
        "--surfaces",
        default=",".join(sorted(DEFAULT_ALLOWED_SURFACES)),
        help=f"comma-separated opted-in surfaces (default: all); known: {sorted(ALL_SURFACES)}",
    )
    args = parser.parse_args()
    allowed = frozenset(s.strip() for s in args.surfaces.split(",") if s.strip())
    unknown = allowed - ALL_SURFACES
    if unknown:
        parser.error(f"unknown surfaces: {sorted(unknown)}")

    buffer = RingBuffer()
    capture = Capture(buffer, allowed)
    capture.start()
    print(f"Capturing on {sorted(allowed)}. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(STATUS_INTERVAL_S)
            print(f"captured: {dict(capture.captured)}  dropped: {dict(capture.dropped)}")
    except KeyboardInterrupt:
        pass
    finally:
        capture.stop()


if __name__ == "__main__":
    main()
