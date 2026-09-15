# OrgRegister

OrgRegister is a local dashboard for managing an email-backed registration workflow, task history, account health checks, proxy testing, and credential presentation.

This repository is a sanitized public edition. It contains no real mailbox credentials, database, session tokens, access tokens, browser profiles, or authenticated request data.

## Setup

```powershell
cd C:\path\to\Reg-pub
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
patchright install chromium
python run.py
```

Open `http://127.0.0.1:8001`.

## Credential format

Create a local `data/emails.txt` (ignored by Git) using six `----`-separated fields:

```text
MS_EMAIL----MS_PASSWORD----MS_UUID----MSA_REFRESH_TOKEN----TEMP_EMAIL----TEMP_PASSWORD
```

Use your own test accounts and tokens. Never commit this file or paste live credentials into issues, logs, screenshots, or documentation.

## Included

- FastAPI backend with SQLite persistence created locally at `data/reg.db`
- Patchright browser workflow and configurable proxy support
- Graph/IMAP mailbox polling abstraction
- Task dashboard, WebSocket progress updates, account health checks
- Sanitized frontend, internationalization, proxy modal, and account/task management actions
- Unit tests under `tests/`

## Verification

```powershell
python -m unittest discover -s tests -q
python -m compileall -q backend run.py tests
```

## Security notes

- Bind the panel to loopback unless you add authentication and TLS.
- Treat mailbox passwords, MSA refresh tokens, Session Tokens, and Access Tokens as secrets.
- The included registration workflow is for authorized testing and research environments only.
