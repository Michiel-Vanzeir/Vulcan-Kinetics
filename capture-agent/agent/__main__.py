"""Run the capture agent: python -m agent [--backend-url URL] [--surfaces teams_desktop,gmail_web].

Prints each payload exactly as it would be sent: counts, flags, ids and topic tokens.
Typed text is never printed, logged or written anywhere.
"""

import argparse
import os

from agent.backend_payload import BackendPayloads
from agent.buffer import RingBuffer
from agent.capture import Capture
from agent.config import ALL_SURFACES, DEFAULT_ALLOWED_SURFACES
from agent.pipeline import Pipeline
from agent.sender import Sender
from signal_detector import DetectorConfig, SignalDetector


def main() -> None:
    parser = argparse.ArgumentParser(description="whoknows capture agent")
    parser.add_argument(
        "--surfaces",
        default=",".join(sorted(DEFAULT_ALLOWED_SURFACES)),
        help=f"comma-separated opted-in surfaces (default: all); known: {sorted(ALL_SURFACES)}",
    )
    parser.add_argument(
        "--user-id",
        default=os.environ.get("WHOKNOWS_USER_ID", "emp_014"),
        help="user id sent with every payload (env WHOKNOWS_USER_ID)",
    )
    parser.add_argument(
        "--backend-url",
        default=os.environ.get("WHOKNOWS_BACKEND_URL"),
        help="POST payloads here (env WHOKNOWS_BACKEND_URL); without it nothing leaves the machine",
    )
    parser.add_argument("--quiet", action="store_true", help="don't print payloads")
    args = parser.parse_args()
    allowed = frozenset(s.strip() for s in args.surfaces.split(",") if s.strip())
    unknown = allowed - ALL_SURFACES
    if unknown:
        parser.error(f"unknown surfaces: {sorted(unknown)}")

    sender = Sender(args.backend_url, echo=not args.quiet)
    detector = SignalDetector(DetectorConfig(user_id=args.user_id))
    pipeline = Pipeline(RingBuffer(), detector, BackendPayloads(), sender)
    capture = Capture(pipeline, allowed)
    sender.start()
    capture.start()

    destination = args.backend_url or "nowhere (demo mode, printing only)"
    print(f"whoknows agent for {args.user_id}, sending to {destination}.")
    print("Type in Teams, Outlook, Gmail, ... Ctrl+Alt+W = ask now. Ctrl+C to stop.")
    try:
        capture.wait()
    except KeyboardInterrupt:
        pass
    finally:
        capture.stop()
        sender.stop()
        print(f"\npayloads: {pipeline.payloads}  sent: {sender.sent}  failed: {sender.failed}"
              f"  rejected: {sender.rejected}")
        print(f"keys captured: {dict(capture.captured)}  dropped: {dict(capture.dropped)}")


if __name__ == "__main__":
    main()
