Chat Room — Summary & Run Instructions

Overview

This repository is a small Flask chat application ("River Secondary School Gossip"). Recent edits focused on:

- Fixing admin access control and making the `admin_required` decorator flexible.
- Allowing authenticated users to start a private admin chat and adding rate-limiting for that endpoint (Flask-Limiter integrated; Redis supported as optional storage).
- Adding a modal confirmation UI and replacing native confirm() calls in chat/pending flows.
- Improving mobile UX: responsive CSS, off-canvas sidebar, mobile header with a hamburger, and small-screen typography tweaks.
- Fixed template/asset issues: removed stray inline <style>, fixed JS syntax in reward wheel, and resolved several template-Jinja/JS quoting issues.

Files changed (high level)

- `app.py` — auth decorators, limiter integration (requires `flask_limiter` and optional Redis).  
- `templates/chat.html`, `templates/pending.html`, `templates/reward.html`, `templates/admin.html` — modal includes, mobile header placeholders, removed inline-style problems.  
- `templates/particals/confirm_modal.html` — added modal partial.  
- `static/style.css` — responsive rules, off-canvas sidebar, small-screen fixes, `.lock-dot`, `.user-support-badge`.  
- `static/script.js` — modal helper, off-canvas toggle, backdrop & ESC handler, mobile header injection.  
- `static/reward_wheel.js` — fixed JS syntax and made `updateRecentWinners` a proper prototype method.  
- `static/admin.js` — reveal-field helper updated to read `data-value` attributes.  

Quick start (PowerShell)

# From the project root (Windows PowerShell)
```powershell
# 1) Activate the virtualenv (if using the included .venv)
& ".\.venv\Scripts\Activate.ps1"

# 2) Install Python dependencies (ensure pip is up-to-date)
python -m pip install --upgrade pip
pip install -r .\requirements.txt

# 3) (Optional) Start Redis locally for production-like rate-limiting
# If you have Docker installed:
docker run -d -p 6379:6379 --name chatroom-redis redis:7
# Then set the REDIS_URL env var in PowerShell (example):
$env:REDIS_URL = 'redis://127.0.0.1:6379/0'

# 4) Set Flask env variables and run the app
$env:FLASK_APP = 'app.py'
$env:FLASK_ENV = 'development'  # remove or set to 'production' for prod
# If you have a SECRET_KEY / DB URI, export them similarly:
# $env:SECRET_KEY = 'a-very-secret-key'
# $env:SQLALCHEMY_DATABASE_URI = 'sqlite:///instance/app.db'

flask run --host=0.0.0.0 --port=5000
```

Notes on the rate limiter

- The limiter is integrated via `Flask-Limiter`. If `REDIS_URL` is set the limiter uses Redis storage (recommended for multi-process deployments). If Redis is not configured, the app may fall back to an in-memory limiter (dev only) or a warning will be logged.
- The rate for the admin chat endpoint is configurable via an environment variable (see `app.py` for `ADMIN_CHAT_RATE`, default is `3 per 10 minutes`).

Running tests

- Tests are written with pytest. To run:
```powershell
& ".\.venv\Scripts\Activate.ps1"
python -m pytest -q
```

If pytest is not installed, add it to your venv with `pip install pytest` or `pip install -r requirements.txt` if included.

Developer notes & next steps

- Mobile UX: The off-canvas CSS is in place; the JS toggles/backdrop/ESC handler were added. Manually test on a real phone or via responsive browser to verify the behavior and adjust spacing.
- Redis: For production deployments, run Redis (or a managed Redis) and set `REDIS_URL`. This enables robust cross-process rate-limiting.
- Security: Ensure `SECRET_KEY` and DB credentials are set as environment variables in production. Consider HTTPS and proper CORS if exposing publicly.
- Remaining housekeeping: tidy up or remove dev-only scripts, add integration tests for the admin endpoints, and consider adding small Selenium or Playwright tests for the mobile UI flows.

Contact

If you want, I can:
- Run the test suite in your venv now.
- Install missing dependencies into the venv (pip) and run pytest.
- Add a small automated smoke test for the mobile off-canvas toggle.

Tell me which of these you want next.
