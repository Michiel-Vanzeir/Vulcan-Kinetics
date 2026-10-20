"""Run the capture agent: python -m agent [--backend-url URL] [--surfaces teams_desktop,gmail_web].

Settings come from the environment or capture-agent/.env (see agent/config.py); flags override.

Prints each payload exactly as it would be sent: counts, flags, ids and topic tokens.
Typed text is never printed, logged or written anywhere.
"""

import argparse
from dataclasses import replace

from agent.buffer import RingBuffer
from agent.capture import Capture
from agent.config import ALL_SURFACES, DEFAULT_ALLOWED_SURFACES, load_config
from agent.panel import PanelWindow
from agent.pipeline import Pipeline
from agent.transport import Transport
from signal_detector import DetectorConfig, SignalDetector


def main() -> None:
    parser = argparse.ArgumentParser(description="whoknows capture agent")
    parser.add_argument(
        "--surfaces",
        default=",".join(sorted(DEFAULT_ALLOWED_SURFACES)),
        help=f"optional surface restriction; backend consent is always required: {sorted(ALL_SURFACES)}",
    )
    parser.add_argument("--user-id", help="user id sent with every payload (WHOKNOWS_USER_ID)")
    parser.add_argument(
        "--backend-url",
        help="backend base URL (WHOKNOWS_BACKEND_URL); without it nothing leaves the machine",
    )
    parser.add_argument("--quiet", action="store_true", help="don't print payloads")
    parser.add_argument(
        "--no-panel", action="store_true", help="don't open the popup (Ctrl+Alt+W or doubt)"
    )
    args = parser.parse_args()
    allowed = frozenset(s.strip() for s in args.surfaces.split(",") if s.strip())
    unknown = allowed - ALL_SURFACES
    if unknown:
        parser.error(f"unknown surfaces: {sorted(unknown)}")

    config = load_config()
    if args.user_id:
        config = replace(config, user_id=args.user_id)
    if args.backend_url:
        config = replace(config, backend_url=args.backend_url.rstrip("/"))

    panel = None if args.no_panel else PanelWindow()
    on_doubt = panel.open_unless_shown if panel is not None else None
    transport = Transport(config, echo=not args.quiet, on_doubt=on_doubt)
    detector = SignalDetector(DetectorConfig(user_id=config.user_id))
    pipeline = Pipeline(
        RingBuffer(), detector, transport, show_experts=not args.quiet, panel=panel
    )
    transport.start_consent_polling()
    capture = Capture(pipeline, allowed, policy=lambda: transport.capture_policy()
                      & (allowed or ALL_SURFACES))
    capture.start()

    destination = config.backend_url or "nowhere (demo mode, printing only)"
    print(f"whoknows agent for {config.user_id}, sending to {destination}.")
    print("Enable desktop capture in Account settings. Ctrl+Alt+W opens the panel in opted-in fields.")
    try:
        capture.wait()
    except KeyboardInterrupt:
        pass
    finally:
        capture.stop()
        transport.close()
        if panel is not None:
            panel.close()
        print(f"\npayloads: {pipeline.payloads}  sent: {transport.sent}  retried: {transport.retried}"
              f"  dropped: {transport.dropped}  rejected: {transport.rejected}")
        print(f"keys captured: {dict(capture.captured)}  dropped: {dict(capture.dropped)}")


if __name__ == "__main__":
    main()
