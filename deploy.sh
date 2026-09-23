#!/usr/bin/env bash
#
# Deploy the Django app.
#
# Install once as a git hook so that `git pull` deploys by itself:
#
#     cd ~/repositories/dhaubanjar-nirman-sewa
#     chmod +x deploy.sh
#     ln -sf ../../deploy.sh .git/hooks/post-merge
#
# After that, deploying is just:
#
#     cd ~/repositories/dhaubanjar-nirman-sewa && git pull
#
# Run it by hand any time with: ./deploy.sh

set -euo pipefail

# Locating the repo is the one genuinely fiddly part. As a git hook this
# file is reached through the SYMLINK at .git/hooks/post-merge, and bash
# reports the symlink's own path in BASH_SOURCE without resolving it - so
# dirname alone lands in .git/hooks, not the repo. Git knows better, and it
# runs hooks from the top of the working tree, so ask it first.
SRC="$(git rev-parse --show-toplevel 2>/dev/null || true)"

if [ -z "$SRC" ] || [ ! -e "$SRC/manage.py" ]; then
  SELF="${BASH_SOURCE[0]}"
  if command -v readlink >/dev/null 2>&1; then
    SELF="$(readlink -f "$SELF" 2>/dev/null || echo "$SELF")"
  fi
  SRC="$(cd "$(dirname "$SELF")" && pwd)"
fi

for required in manage.py config/settings.py requirements.txt; do
  if [ ! -e "$SRC/$required" ]; then
    echo "ERROR: $SRC does not look like the app (missing $required)" >&2
    exit 1
  fi
done

cd "$SRC"

# The virtualenv is not active inside a git hook, so call its python directly.
VENV_PY="${VENV_PY:-$HOME/virtualenv/repositories/dhaubanjar-nirman-sewa/3.11/bin/python}"
if [ ! -x "$VENV_PY" ]; then
  echo "ERROR: virtualenv python not found at $VENV_PY" >&2
  echo "       set VENV_PY=/path/to/bin/python and re-run." >&2
  exit 1
fi

echo "==> collectstatic"
# Not optional: filenames are content-hashed, so skipping this leaves the
# manifest pointing at files that no longer exist and the site 500s.
"$VENV_PY" manage.py collectstatic --noinput

echo "==> migrate"
"$VENV_PY" manage.py migrate --noinput

echo "==> restart"
# Passenger reloads when this file's mtime changes.
mkdir -p tmp && touch tmp/restart.txt

echo "Deployed $(git -C "$SRC" rev-parse --short HEAD 2>/dev/null || echo '?')"
echo
echo "NOTE: index.html, robots.txt and sitemap.xml are served by Django now."
echo "      They must NOT exist in the document root - Apache would serve"
echo "      them and Passenger would never see the request."
