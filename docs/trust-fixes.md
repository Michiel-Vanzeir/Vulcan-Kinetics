# Jury review follow-up

Implemented on `thoma/trust-fixes`:

1. Topic searches request `/experts`; directory fixtures no longer determine signal ranks.
   Backend failures and gaps are visible, without a synthetic best-match fallback.
2. Explicit preview replies have recorded question context and measured writing inputs.
   With separate consent, only derived counts and topic ids reach the signal backend.
   Desktop reply detection remains unsupported and is no longer claimed.
3. Capture defaults off, with persisted app opt-ins and topic exclusions. The agent polls
   expiring consent, and backend ingestion rechecks it atomically with scoring.
4. Sensitive-field checks precede bounded raw-event queueing. Focus is checked again before
   processing and timed emissions. Browser capture is disabled rather than trusting titles.
5. Backend authentication binds employee ingestion to a configured identity. Graph endpoints
   require a separate administrator credential. Preview credentials remain server-side.
6. Employee/session/compose context identities, persisted replay watermarks and per-context
   evidence credits prevent cumulative snapshots from multiplying answer evidence.
7. Every requested topic is preserved, including countries. Missing matches show separate
   knowledge gaps; a general topic match does not establish country-specific expertise.
8. Rankings are labelled heuristic and require three credited answer contexts. Unsupported
   claims about correctness, implicit vouches, broad browser capture and signed deployment
   were removed from the current implementation description.

There is no honest code-only fix for missing empirical evidence. Real-world accuracy,
Windows accessibility behaviour, deployment security and a fresh Aikido scan still require
independent validation. The study plan and current limitations are in `trust-validation.md`.
