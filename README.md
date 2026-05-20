# Worklog; Deliberately Vulnerable Django App

A minimal hour-tracking Django app built for the **Cybersecurity Base -
Course Project I** (University of Helsinki). It contains five intentional,
exploitable security flaws drawn from the **OWASP Top 10 (2021)**, each
paired with the corresponding fix as a commented-out block in the same file.

> ⚠️  This application is intentionally insecure. Do **not** deploy it,
> connect it to a real database, or expose it on a public network.

## Flaws covered

| # | OWASP 2021 category                              | Where                              |
|---|--------------------------------------------------|------------------------------------|
| 1 | A01 Broken Access Control (IDOR)                 | `tracker/views.py` (entry detail/edit) |
| 2 | A02 Cryptographic Failures (plaintext PIN)       | `tracker/models.py`, `tracker/views.py` |
| 3 | A03 Injection (SQL injection in search)          | `tracker/views.py` (entry list)    |
| 4 | A05 Security Misconfiguration                    | `worklog/settings.py`              |
| 5 | A07 Identification & Authentication Failures     | `worklog/settings.py`, `tracker/views.py` |

Every flaw is documented inline like:

```python
# === FLAW N: AXX <category> ===
# <what is wrong>
# See README section "Reproducing Flaw N" for steps.
<vulnerable code>

# === FIX (commented out — uncomment to apply) ===
# <fixed code>
```

To switch a flaw to its fixed form, open the file, comment out the
vulnerable block, and uncomment the fix block. No branches or git tags
are used - both forms always live side-by-side in the same file.

## Installation

```bash
git clone <this repo>
cd cyberproject
python3 -m venv venv
source venv/bin/activate         # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser # for the team-summary / admin pages
python manage.py runserver
```

The app then runs at <http://127.0.0.1:8000/>.

Useful URLs:

- `/accounts/register/` — create a regular user
- `/accounts/login/`    — log in
- `/`                   — your own entries (list + search)
- `/new/`               — create entry
- `/<id>/`              — entry detail
- `/team/`              — staff-only team summary
- `/profile/pin/`       — set your secondary PIN
- `/admin/`             — Django admin

## Reproducing the flaws

> The numbered sections below are filled in as each flaw is introduced.

### Reproducing Flaw 1 - A01 Broken Access Control (IDOR)

The `entry_detail` and `entry_edit` views in `tracker/views.py` look up a
`TimeEntry` by primary key with no ownership check. Any logged-in user can
read or modify another user's entry by tampering with the integer in the
URL.

**Setup**

1. Register two users at `/accounts/register/`, e.g. `alice` and `bob`.
2. Log in as `alice`, create a time entry at `/new/` (e.g. project
   "Alice private notes"). Note its URL — it will be something like
   `/1/`.
3. Log out, log in as `bob`. Create one of his own at `/new/` so Bob has
   an entry that legitimately belongs to him (e.g. `/2/`).

**Exploit (before)**

4. While still logged in as **Bob**, navigate to `/1/` (Alice's entry).
   You will see Alice's project name, hours and description.
5. Navigate to `/1/edit/` — Bob can submit changes and overwrite Alice's
   entry. After saving, log back in as Alice and confirm the data is
   changed.

Screenshot suggestions: `flaw-1-before-detail.png` (Bob viewing
`/1/` showing `Owner: alice`), `flaw-1-before-edit.png` (Bob's edit
form pre-filled with Alice's data).

**Fix (after)**

6. In `tracker/views.py`, in both `entry_detail` and `entry_edit`,
   comment out the line `entry = get_object_or_404(TimeEntry, pk=pk)`
   and uncomment the `entry = get_object_or_404(TimeEntry, pk=pk,
   owner=request.user)` line below it.
7. Repeat step 4: Bob requesting `/1/` now gets a **404 Not Found** —
   the same response as a non-existent entry, so existence isn't leaked.

Screenshot suggestion: `flaw-1-after-404.png` (Bob requesting `/1/`,
seeing 404).

### Reproducing Flaw 2 - A02 Cryptographic Failures

The `Profile.set_pin` / `Profile.check_pin` methods in `tracker/models.py`
store the user's secondary PIN as **cleartext** in the database. The PIN
is then used as a confirmation gate when deleting a time entry. Note
that Django's password storage (the user's main login password) is
untouched — only this parallel PIN field is broken on purpose.

**Setup**

1. Log in as any user (e.g. `alice`).
2. Go to `/profile/pin/` and set a PIN such as `1234`.

**Exploit (before) — option A: shell**

3. From the project root run:
   ```bash
   sqlite3 db.sqlite3 'select user_id, pin from tracker_profile;'
   ```
   The output prints the raw PIN, e.g. `1|1234`. → `flaw-2-before-sqlite.png`

**Exploit (before) — option B: Django admin**

3. Create a superuser if you haven't (`python manage.py createsuperuser`),
   log in to `/admin/`, open **Tracker → Profiles**. The list view shows
   each user's PIN in the clear. → `flaw-2-before-admin.png`

**Fix (after)**

4. In `tracker/models.py`, comment out the plaintext `set_pin` /
   `check_pin` methods and uncomment the hashed pair below them (which
   uses `make_password` / `check_password`).
5. Reset Alice's PIN through `/profile/pin/` once more (the old plaintext
   value won't validate after the switch).
6. Re-run the sqlite query — the `pin` column now contains a PBKDF2 hash
   like `pbkdf2_sha256$600000$...$...`, not `1234`. The delete flow at
   `/<id>/delete/` still works with the original PIN value. →
   `flaw-2-after-sqlite.png`

### Reproducing Flaw 3 - A03 Injection (SQL injection)

The search filter on the entry list (`entry_list` in `tracker/views.py`)
builds its SQL with `cursor.execute(f"... LIKE '%{query}%' ...")` —
direct f-string interpolation of the user-supplied `q` parameter into
the SQL string.

**Setup**

1. Make sure there are at least two users with at least one entry each
   (the curl seed already creates `alice` with "Alice private notes"
   and `bob` with "Bob secret work").

**Exploit (before)**

2. Log in as **alice**.
3. Visit `/`, type `Alice` into the search box and submit. Only Alice's
   own row appears, as expected. → `flaw-3-before-normal.png`
4. In the search box paste the payload exactly: `%') OR 1=1 -- `
   (note the trailing space). Submit. The list now shows Alice's row
   **and Bob's row** ("Bob secret work" / owner `bob`) — the owner
   filter was bypassed via SQL injection. → `flaw-3-before-inject.png`

   You can also fire it directly with curl:
   ```bash
   curl -b alice.cookies \
     "http://127.0.0.1:8000/?q=%25%27%29%20OR%201%3D1%20--%20"
   ```

**Fix (after)**

5. In `tracker/views.py`, in `entry_list`, comment out the f-string `sql
   = (...)` block plus the `cursor.execute(sql)` / `rows = ...` lines,
   and uncomment the ORM block (`entries = TimeEntry.objects.filter(
   owner=request.user).filter(Q(project__icontains=query) |
   Q(description__icontains=query))`).
6. Re-submit the same payload `%') OR 1=1 -- ` in the search field.
   The list is empty: the ORM treats the payload as literal text and
   nothing matches. → `flaw-3-after-inject.png`

### Reproducing Flaw 4 - A05 Security Misconfiguration

Three production-unsafe defaults are active in `worklog/settings.py` at
the same time: `DEBUG = True`, `ALLOWED_HOSTS = ['*']`, and the
`SECRET_KEY` is hardcoded in the source rather than read from the
environment. The `tracker/views.py:debug_error` view (URL
`/debug-error/`) is a small demo trigger — any unhandled exception
would do; it just gives you a reliable way to reach the debug page.

**Exploit (before)**

1. Visit `http://127.0.0.1:8000/debug-error/` in your browser. Django
   renders its yellow debug page with:
   - the full traceback,
   - the request `META` (headers, env),
   - the installed apps list and middleware,
   - the SQL queries that ran,
   - the local variables in every frame.
   → `flaw-4-before-debug-page.png`

2. Open `worklog/settings.py` — the `SECRET_KEY` value is sitting in
   plain source. Anyone who clones the repo can use it to forge
   sessions or password-reset tokens. → `flaw-4-before-secret-key.png`

3. Hit the app with a spoofed `Host` header — `ALLOWED_HOSTS = ['*']`
   means the server accepts any value:
   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" \
        -H "Host: evil.example.com" http://127.0.0.1:8000/accounts/login/
   # → 200
   ```
   → `flaw-4-before-host-header.png` (optional)

**Fix (after)**

4. In `worklog/settings.py`, comment out the three lines under
   `# === FLAW 4 ===` (`SECRET_KEY = '...'`, `DEBUG = True`,
   `ALLOWED_HOSTS = ['*']`) and uncomment the three lines under
   `# === FIX ===`.
5. Provide a real key in the environment before starting the server:
   ```bash
   export DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(50))')"
   python manage.py runserver
   ```
6. Visit `/debug-error/` again. Instead of a yellow debug page you get
   Django's bare-bones `Server Error (500)` — no traceback, no
   settings, no SECRET_KEY. → `flaw-4-after-500.png`
7. The same `curl -H "Host: evil.example.com"` now returns **400 Bad
   Request** with `DisallowedHost` because the host isn't in
   `ALLOWED_HOSTS`. → `flaw-4-after-host-header.png` (optional)

Note: with `DEBUG = False` Django no longer serves static files from
`STATICFILES_DIRS` for you; the login/admin pages still work but may
render unstyled. That is expected — the fix is correct.

### Reproducing Flaw 5 - A07 Identification & Authentication Failures

The flaw spans two files and both halves must be fixed together:

- `worklog/settings.py` — `AUTH_PASSWORD_VALIDATORS = []` (empty), so
  any call to `validate_password()` is a no-op.
- `tracker/views.py:register` — the view never calls
  `validate_password()` at all; it just hashes whatever the user typed
  and saves a new account.

**Exploit (before)**

1. Go to `/accounts/register/`.
2. Choose any of the following obviously weak passwords. All of them
   create a fully working account that's auto-logged in:
   - `1`
   - `abc`
   - `password`
   - `12345`
   - the username itself (would normally fail
     `UserAttributeSimilarityValidator`)
3. Watch the redirect to `/` succeed and the entry list render. The
   weak account is fully usable. → `flaw-5-before-register.png`

   Bonus terminal evidence:
   ```bash
   sqlite3 db.sqlite3 "select id, username, length(password) from auth_user;"
   ```
   The new row exists with a normally-hashed password — the issue is
   not how it's stored, it's that the cleartext input was never
   checked.

**Fix (after)**

4. In `worklog/settings.py`, comment out the `AUTH_PASSWORD_VALIDATORS
   = []` line and uncomment the populated list below it (under the
   `# === FIX ===` header).
5. In `tracker/views.py`, in `register`, uncomment the block under
   `# === FIX ===`:
   ```python
   from django.contrib.auth.password_validation import validate_password
   from django.core.exceptions import ValidationError
   try:
       validate_password(password, User(username=username))
   except ValidationError as exc:
       errors.extend(exc.messages)
   ```
6. Repeat the registration with password `1`. The form now re-renders
   with the validator messages, e.g. "This password is too short. It
   must contain at least 8 characters." and "This password is too
   common." No user is created. → `flaw-5-after-rejected.png`
7. Try a strong password (e.g. `correcthorsebatterystaple1`) — that
   still succeeds.

## Screenshots

See `screenshots/README.md` for the naming convention used for the
before/after evidence images.
