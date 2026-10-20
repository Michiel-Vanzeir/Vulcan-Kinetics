# Aikido dependency remediation

Checked on 2026-10-20. The lockfile already selected the following versions, but the
project manifest permitted vulnerable older releases when resolving without that lock.
The manifest now enforces these baselines and the lockfile was regenerated with uv.

| Package | Minimum and currently locked version |
|---|---|
| python-dotenv | 1.2.4 |
| sentence-transformers | 6.1.0 |
| transformers | 5.20.2 |
| tokenizers | 0.23.3 |

`transformers` and `tokenizers` were already present transitively in the optional ML
extra. They now have explicit constraints. No packages or environment variables were added.
The capture-agent test requirements already pin `python-dotenv==1.2.4`.

The model loader explicitly sets `trust_remote_code=False` and requires safetensors.
Real embeddings remain optional; the popup's signal-ranking path does not load ML models.

## Advisory references

- [sentence-transformers code-execution advisory](https://github.com/advisories/GHSA-jhr6-gm9c-rqjv):
  patched in 5.6.0; the project requires 6.1.0 or newer.
- [transformers code-execution advisory](https://github.com/advisories/GHSA-29pf-2h5f-8g72):
  patched in 5.3.0; the project requires 5.20.2 or newer.
- [python-dotenv symlink advisory](https://github.com/theskumar/python-dotenv/security/advisories/GHSA-mf9w-mj56-hr94):
  patched in 1.2.2; the project requires 1.2.4 or newer.
- [tokenizers upstream releases](https://github.com/huggingface/tokenizers/releases):
  the 0.23.1 release includes HTML escaping for EncodingVisualizer output;
  the project requires 0.23.3 or newer. The application does not use that visualizer.

## Verification

A targeted `pip-audit --no-deps --disable-pip` run against all four exact locked versions
reported **No known vulnerabilities found**. A second audit of `uv export --locked
--all-extras`, including optional ML dependencies for the current Python environment,
also reported **No known vulnerabilities found**. All 292 Python regression tests passed,
including a check that the model constructor keeps both loading protections enabled.
This queries the public advisory database;
it is not an Aikido rescan and cannot confirm closure of an alert with a different CVE.

For reproducible installation, use `uv sync --locked`, adding `--extra ml` when needed.
After publishing the change, rescan the latest commit in Aikido and confirm that its
dependency inventory uses `Neo4J-backend/uv.lock` rather than an older commit or manifest.
