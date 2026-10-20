# Signal detector

Turns a stream of `KeyEvent`s into counted `SignalPayload`s per compose context (one focused
text field in one app). It measures and doesn't interpret: the backend scoring module turns
these counts into TYPING / HESITATING / STRUGGLING.

- Input: `KeyEvent` streams produced by the capture agent (`../agent/`). Wiring the two is out
  of scope here; the detector is tested with synthetic streams (`../tests/test_signal_detector.py`).
- Output: `SignalPayload`, the payload sent to the backend. The field list and the "explicitly
  NOT sent" list are the contract, in `IDEA.md` under "Signal detector output".
- Privacy proof: `SignalDetector.build_payload()` in `detector.py` is the only function that
  produces a payload. It never reads the private text window, and `SignalPayload` has no field
  that can carry text (enforced by `test_payload_has_no_free_text_fields`).

## Usage

```python
from signal_detector import DetectorConfig, KeyEvent, KeyKind, SignalDetector

detector = SignalDetector(DetectorConfig(user_id="u_1234", device_id="d_77"))
payload = detector.handle_event(KeyEvent(ts=..., kind=KeyKind.CHAR, char="a",
                                         surface="gmail_web", context_id="c_1"))
detector.tick()                # call every ~100 ms: fires pause / ellipsis / idle-flush triggers
detector.manual_trigger("c_1") # from the hotkey
detector.get_baseline("u_1234")
```

`handle_event` returns at most one payload, carrying the most specific trigger:
deletion burst > hedge word > placeholder > punctuation > pause > idle flush.

## Files

| File | Role |
|---|---|
| `events.py` | `KeyEvent`, `SignalPayload` and the enums (`KeyKind`, `Trigger`, `PlaceholderKind`) |
| `detector.py` | `SignalDetector`, `DetectorConfig`, per-context state, triggers, `build_payload()` |
| `hedges.yaml` / `hedges.py` | Hedge list per language (EN/NL/FR/DE, ~300 phrases) and the whole-word matcher (set lookup on the last words; ignores case, accents, apostrophes) |
| `placeholders.py` | `[...]`, `<...>`, `xxx`, `???`, trailing `...` |
| `baseline.py` | Rolling per-user baseline (EMA of inter-key gap and deletion rate) |

## Behaviour notes

- A `.` or `,` only counts once whitespace follows, so decimals (`3.5`) and emails don't fire
  punctuation or hedge triggers. `?` and `!` fire immediately.
- An email is detected when `@` is typed: the token typed so far is masked retroactively.
- A `submit` event (field sent or cleared) emits a final `submit` payload and resets the context.
