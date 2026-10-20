# AGENTS.md: Team Rules for AI Coding Assistants

This file is the **single source of truth** for how code is written in this repo.
It is read by ChatGPT/Codex (`AGENTS.md`) and imported by Claude Code (`CLAUDE.md`).
Four teammates work in parallel, each with their own AI assistant, so the code has to look like one person wrote it.

> If you change a rule, change it **here**. Never put conflicting rules in `CLAUDE.md`.

---

## 0. Before you start any task

1. Read `IDEA.md`. It describes what we are building *right now*. Do not build features that aren't listed there.
2. Run `git pull` (or ask the human to) before you start editing. Four people are pushing all the time.
3. Stay inside the area of the task you were given. Don't refactor, rename, or reformat files you weren't asked to touch. That causes merge conflicts for the others.
4. If the task changes the idea or scope, update `IDEA.md` in the same change (see section 7).

### `previous-round/`: reference only

`previous-round/` holds our code from the previous hackathon round (a WXT browser extension plus a Python backend). It is **not** part of the current project, and its code quality is poor.
- Never edit, run, build, or import from it, and don't add it to tooling (lint, tests, build).
- You may *read* it for ideas, domain logic, or data, but rewrite anything you reuse so it follows the rules in this file. Don't copy its patterns or structure.
- Ignore it when you search the codebase unless the human asks about it.
- **It must be deleted before submission** (see the checklist in `IDEA.md`). If the human mentions submitting, the final Aikido scan, or wrapping up, and the folder still exists, remind them.

## 1. Project stack

> **TODO (fill in the remaining TBDs when decided).**

- Extension: Chrome extension, Manifest v3, TypeScript (build tool _TBD_)
- Backend: Python, FastAPI or Flask (_TBD_)
- Data: synthetic JSON only, never real or confidential data
- Package manager: _TBD_ (use only this one; never mix npm/yarn/pnpm, or pip/poetry/uv)
- How to run locally: _TBD_ (keep `README.md` in sync)
- How to run tests / lint / format: _TBD_

Don't add a new dependency unless you have to. If you add one, say so explicitly in your summary so the team can approve it. Prefer what is already installed.

## 2. Language

- **All code, comments, commit messages, branch names, and docs are in English**, even though the team speaks Dutch.
- Answer the human in the language they wrote to you in.

## 3. Code style

General:
- Formatting comes from `.editorconfig` and the formatter for the stack (to be defined in section 1). Don't hand-format against it.
- Indentation is 2 spaces for JS/TS/JSON/YAML/HTML/CSS and 4 spaces for Python. Line endings are LF. Files end with a newline.
- Keep lines under about 100 characters.
- Write small functions that each do one thing. Choose readable code over clever code. This is a hackathon, but other people still have to read it tomorrow morning.
- No dead code, no commented-out code blocks, no leftover `console.log` / `print` debugging.
- Don't silently swallow errors. Show a useful message, or let it fail loudly.

Naming:
| Thing | Convention | Example |
|---|---|---|
| Variables, functions (JS/TS) | camelCase | `fetchUserScore` |
| Variables, functions (Python) | snake_case | `fetch_user_score` |
| Classes, types, React components | PascalCase | `ScoreCard` |
| Constants | UPPER_SNAKE_CASE | `MAX_RETRIES` |
| Files (JS/TS) | kebab-case, components PascalCase | `api-client.ts`, `ScoreCard.tsx` |
| Files (Python) | snake_case | `api_client.py` |
| Env vars | UPPER_SNAKE_CASE | `OPENAI_API_KEY` |

Names should be descriptive. Avoid `data`, `temp`, `x2`, `handleStuff`.

## 4. Comments

- Comments explain **why**, not what. Leave out comments that just restate the code.
- Every non-trivial function or module gets a one-line docstring/JSDoc saying what it's for.
- Use `TODO(name): ...` for unfinished work, with the teammate's first name, so it's clear who owns it.
- Use `HACK: ...` for a shortcut taken because of time pressure that must be revisited before the demo.
- Don't add AI-flavoured comments like "Here we now carefully...", "This function elegantly...", or "Added by Claude/ChatGPT".

## 5. Git workflow (4 people, 1 repo)

- `main` must **always run** because it's what we demo. Never push broken code to `main`.
- Work on short-lived branches: `<name>/<short-topic>`, e.g. `michiel/login-page`.
- Commit small and often. Pull/rebase from `main` often (at least every hour).
- Use Conventional Commits for messages: `feat: ...`, `fix: ...`, `refactor: ...`, `docs: ...`, `chore: ...`, `style: ...`, `test: ...`. Write in the imperative mood and keep the subject under 72 characters.
- AI assistants **don't commit, push, merge, or force-push unless the human asks**. Never rewrite history on `main`.
- If you hit a merge conflict in a file someone else owns, stop and tell the human. Don't guess.
- Lockfiles (`package-lock.json`, `poetry.lock`, etc.) get committed. If one conflicts, regenerate it; don't hand-merge it.

## 6. Secrets and safety

- **Never commit secrets.** API keys go in `.env` (which is git-ignored). Keep `.env.example` up to date with every variable name and a dummy value.
- Never print secrets in logs or in the UI.
- Don't hardcode personal paths (`C:\Users\...`). Use relative paths or config.
- We're on mixed OSes (at least Windows). Use cross-platform scripts and paths.

## 7. Idea log (`IDEA.md`): mandatory upkeep

`IDEA.md` describes the idea (problem, core idea, flow, architecture, branding). Three parts need special care:

1. **Features**: the table of what we're building, with a status (`planned`, `in progress (name)`, or `done`) and an owner.
   - Only features we're actually building or have built belong here.
   - When a feature is dropped, **delete its row and every description of it elsewhere in `IDEA.md`** (user flow, architecture, extra-challenge table, project description). Don't strike it through and don't move it to a "maybe later" list. Anyone reading the file must see only the real scope.
2. **Not building**: a short list of deliberate boundaries (things people might be tempted to build). This list isn't a backlog. Never build anything on it.
3. **Changelog**: an append-only, timestamped log of how the *idea* evolved: pivots, scope cuts, key decisions, and why.
   - Format: `- YYYY-MM-DD HH:MM (name): what changed and why`.
   - Keep it to idea-level changes. Don't log every bug fix (git does that).
   - A scope cut may be logged as one line ("cut X to focus on Y") so the reasoning isn't lost. But the cut feature must never reappear in the *Current idea* section, and AI assistants must **never treat changelog entries as things to build**.

When a task adds, finishes, or removes a feature, the assistant updates `IDEA.md` as part of the same change.

## 8. Keep the demo in mind

- Choose working end-to-end over perfect parts. Hardcoded or mock data is fine if it's marked `HACK:`.
- Don't start large rewrites in the final hours. Hard deadline: **16:00**.
- The pitch is presented from a deck, not a live device, so UI states must look good in screenshots.
- Security is scored by an Aikido scan: validate input, check authorisation server-side on every ID, keep dependencies minimal and up to date.
- Follow the branding in `IDEA.md` (colours, font, lowercase "whoknows"). UI copy is plain and direct, with no em dashes.
- Keep `README.md` runnable: setup steps, env vars, and the run command. A judge or teammate must be able to start it from scratch.

## 9. How the AI assistant should behave

- Make the smallest change that solves the task, and match the surrounding code.
- Ask the human before you delete files, change the project structure, swap a library, or change shared config (formatter, linter, build, CI).
- Afterwards, summarise briefly: which files changed, any new dependencies or env vars, and whether `IDEA.md` was updated.
- If a rule here conflicts with a human's request, point out the conflict instead of quietly breaking the rule.
