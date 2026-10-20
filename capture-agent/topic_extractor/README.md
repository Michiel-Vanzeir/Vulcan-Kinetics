# Topic extractor

Recent typing in, topic tokens from a fixed vocabulary out. **Returns a subset of a fixed
vocabulary, never free text.**

```python
from topic_extractor import extract_topics

extract_topics("De opzegtermijn voor een bediende in Spanje, PC 200")
# ['PC_200', 'country_ES', 'notice_period', 'worker_white_collar']
```

- `extract_topics(window, lang_hint=None)` in `extractor.py` is the function that produces
  topic tokens. Every token is validated against `vocab.yaml` before it is returned.
- The window is never returned, logged or stored. Logging is count-level only
  ("extracted 3 topics in 0.6 ms").
- Called by `agent/pipeline.py` once per signal payload, on the ring buffer's text for
  that field, to fill `topics`.

## What it can output

Everything is listed in `vocab.yaml`:

| Token | From |
|---|---|
| `notice_period`, `year_end_bonus`, ... (35 topics) | `topics` |
| `country_BE`, `country_ES`, ... (15 countries) | `entities.country` |
| `PC_200`, `PC_124`, ... | `entities.joint_committee.pattern` |
| `worker_white_collar`, `worker_blue_collar`, `worker_executive` | `entities.worker_class` |

## Pipeline

1. Normalise: lowercase, strip accents, collapse whitespace. Mask email addresses.
2. Joint committees (`PC 200`, `PC200`) and patterns containing digits (`13th month`, `C4`)
   are matched now, before numbers are masked.
3. Mask all digit runs (IBANs, amounts, phone numbers). Split into words; apply `typos.yaml`.
4. Detect the language with langdetect (only trusted for 60+ chars at probability 0.8+),
   otherwise use all of EN/NL/FR. `lang_hint` skips detection.
5. Match: Snowball-stemmed patterns in the detected language(s), plus exact patterns in all
   languages (so a Dutch word in an English mail still counts), plus long Dutch words inside
   compounds (`eindejaarspremieberekening`), plus countries and worker classes.
6. Deduplicate, sort, validate against the vocabulary, return.

Patterns of 1 to 3 letters (`or`, `avg`, `uk`, `cdi`, `rsz`, ...) only match in capitals,
so Dutch `or` (ondernemingsraad) doesn't fire on English "or".

Speed: about 4 ms for a 2000-char window with language detection, under 1 ms with
`lang_hint`. The index is built once at import (about 0.4 s, mostly loading nltk and
langdetect).

## Files

| File | Role |
|---|---|
| `extractor.py` | `extract_topics()`, vocabulary loading and validation |
| `vocab.yaml` | The full vocabulary: topics, countries, PC pattern, worker classes |
| `typos.yaml` | Common misspellings -> canonical spelling |
| `normalize.py` | Lowercase, accents, email/number masking, tokenising, typo map |
| `stems.py` | Snowball stemmers, stemmed pattern index |
| `entities.py` | Countries, joint committees, worker classes |
| `lang_detect.py` | langdetect wrapper that only answers when confident |
