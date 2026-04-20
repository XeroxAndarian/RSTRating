"""
Splits index.html into:
  index.html  - pure login page (redirects to lobby.html if already logged in)
  lobby.html  - authenticated lobby page (redirects to index.html if not logged in)
"""
import re

with open("index.html", "r", encoding="utf-8") as f:
    src = f.read()

# ─────────────────────────────────────────────────────────────────────
#  LOBBY.HTML  — everything from index.html, but:
#   • title changed
#   • auth-shell section removed
#   • hero login buttons removed (only has dark toggle + lobby buttons)
#   • lobby buttons always shown (no renderAppState hiding)
#   • JS: add guard at top of bootstrap(); remove login/register/reset handlers
# ─────────────────────────────────────────────────────────────────────
lobby = src

# Change title
lobby = lobby.replace("<title>RSTRating Leagues</title>", "<title>RSTRating – Lobby</title>")

# Remove the entire auth-shell section from HTML
# It starts with `<section class="content">` and the auth-shell inside it ends just before lobby-shell
lobby = re.sub(
    r'\s*<section class="content">\s*<section class="auth-shell active" id="authShell">.*?</section>\s*\n\s*<section class="lobby-shell"',
    '\n        <section class="content">\n            <section class="lobby-shell"',
    lobby,
    flags=re.DOTALL
)

# Remove the .auth-shell, .lobby-shell display:none CSS (lobby is always visible)
lobby = lobby.replace(
    '''        .auth-shell,
        .lobby-shell {
            display: none;
        }

        .auth-shell.active,
        .lobby-shell.active {
            display: block;
        }''',
    '''        .lobby-shell {
            display: block;
        }'''
)

# Hero: remove any "display:none" on lobby buttons — they're always shown
# The hero has: refresh (display:none), notifbell (display:none), dark, acct (display:none), signout (display:none)
# In lobby.html we want them visible by default (JS still controls signout/acct/etc)
# Actually JS handles this via renderAppState — that's fine. Keep as-is.

# In bootstrap(), add auth-guard redirect
# Current bootstrap starts with: async function bootstrap() {
# We inject right after the opening brace
lobby = lobby.replace(
    "        async function bootstrap() {\n",
    "        async function bootstrap() {\n"
    "            // Auth guard — send unauthenticated users to login page\n"
    "            if (!getToken()) {\n"
    "                window.location.href = './index.html';\n"
    "                return;\n"
    "            }\n"
)

# Change the bootstrap tail to NOT call openTab("login") — go straight to lobby
# Current tail:
#   openTab("login");
#   await refreshAndRender();
#   if (!currentUser) { showStatus(...) }
# Replace with lobby version:
lobby = lobby.replace(
    '            openTab("login");\n'
    '            await refreshAndRender();\n'
    '            if (!currentUser) {\n'
    '                showStatus(inviteTokenFromUrl ? "Invitation detected. Sign in or register to accept it." : "Sign in or register to enter the league lobby.", "ok");\n'
    '            }',
    '            await refreshAndRender();\n'
    '            if (!currentUser) {\n'
    '                // Token present but invalid or server error — redirect to login\n'
    '                window.location.href = \'./index.html\';\n'
    '            }'
)

with open("lobby.html", "w", encoding="utf-8") as f:
    f.write(lobby)
print("lobby.html written")

# ─────────────────────────────────────────────────────────────────────
#  INDEX.HTML  — stripped to login only:
#   • hero: only darkModeToggle (no notifbell/refresh/acct/signout)
#   • lobby-shell section removed
#   • all drawers removed (notif, join, acct)
#   • match overlay + modals removed
#   • JS: add redirect if already logged in; remove all lobby JS
# ─────────────────────────────────────────────────────────────────────
login = src

# Change title
login = login.replace("<title>RSTRating Leagues</title>", "<title>RSTRating – Sign In</title>")

# Hero: remove lobby-only buttons (refresh, notifbell, acct, signout — keep only darkModeToggle)
login = re.sub(
    r'<div class="actions">.*?</div>(?=\s*</div>\s*</section>)',
    '<div class="actions">\n'
    '                    <button class="ghost" id="darkModeToggle" type="button" title="Toggle dark mode" aria-label="Toggle dark mode">🌙</button>\n'
    '                </div>',
    login,
    flags=re.DOTALL,
    count=1
)

# Remove lobby-shell section from HTML
# Lobby shell starts at <section class="lobby-shell" ... and ends at </section> (closing content section)
login = re.sub(
    r'\s*<section class="lobby-shell" id="lobbyShell">.*?</section>\s*</section>\s*</main>',
    '\n            </section>\n        </section>\n    </main>',
    login,
    flags=re.DOTALL
)

# Remove all drawers and modals that are lobby-only
# Notification drawer
login = re.sub(r'\s*<!-- Notification Drawer -->.*?<!-- Account Settings Drawer -->', '\n    <!-- Account Settings Drawer (removed, login page only) -->', login, flags=re.DOTALL)
# Account settings drawer
login = re.sub(r'\s*<!-- Account Settings Drawer.*?-->.*?</div>\s*\n\s*<!-- Match Overlay -->', '\n\n    <!-- Match Overlay (removed) -->', login, flags=re.DOTALL)
# Match overlay
login = re.sub(r'\s*<!-- Match Overlay.*?-->.*?</div>\s*\n\s*<!-- Assist Picker', '\n\n    <!-- Assist Picker', login, flags=re.DOTALL)
# Assist picker
login = re.sub(r'\s*<!-- Assist Picker.*?-->.*?</div>\s*\n\s*<!-- Admin Backdoor', '\n\n    <!-- Admin Backdoor', login, flags=re.DOTALL)
# Backdoor modal
login = re.sub(r'\s*<!-- Admin Backdoor.*?-->.*?</div>\s*\n\s*<script>', '\n\n    <script>', login, flags=re.DOTALL)

# Also remove join drawer if it snuck in
login = re.sub(r'\s*<!-- Join Drawer -->.*?</div>\s*\n\s*<div class="notif-backdrop" id="joinBackdrop"[^>]*></div>', '', login, flags=re.DOTALL)

# In bootstrap(), add redirect if already logged in
login = login.replace(
    "        async function bootstrap() {\n",
    "        async function bootstrap() {\n"
    "            // If already authenticated, go straight to the lobby\n"
    "            if (getToken()) {\n"
    "                window.location.href = './lobby.html';\n"
    "                return;\n"
    "            }\n"
)

# Remove lobby-specific CSS that's not needed on login page (optional — harmless to keep)

with open("index.html", "w", encoding="utf-8") as f:
    f.write(login)
print("index.html written")
print("Done.")
