#!/usr/bin/env bash
#
# Copies the site into the document root.
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

# Overridable so the script can be exercised against a scratch directory:
#     DEPLOYPATH=/tmp/testroot ./deploy.sh
DEPLOYPATH="${DEPLOYPATH:-/home2/madhyapu/dhaubanjarnirmansewa.com.np}"

# Locating the repo is the one genuinely fiddly part. As a git hook this
# file is reached through the SYMLINK at .git/hooks/post-merge, and bash
# reports the symlink's own path in BASH_SOURCE without resolving it - so
# dirname alone lands in .git/hooks, not the repo. Git knows better, and it
# runs hooks from the top of the working tree, so ask it first.
SRC="$(git rev-parse --show-toplevel 2>/dev/null || true)"

# Fallbacks for when this is run directly from outside a repo.
if [ -z "$SRC" ] || [ ! -e "$SRC/index.html" ]; then
  SELF="${BASH_SOURCE[0]}"
  if command -v readlink >/dev/null 2>&1; then
    SELF="$(readlink -f "$SELF" 2>/dev/null || echo "$SELF")"
  fi
  SRC="$(cd "$(dirname "$SELF")" && pwd)"
fi

# Refuse to touch anything unless the source really is the site.
for required in index.html robots.txt sitemap.xml assets/css/styles.css; do
  if [ ! -e "$SRC/$required" ]; then
    echo "ERROR: $SRC does not look like the site (missing $required)" >&2
    exit 1
  fi
done

if [ ! -d "$DEPLOYPATH" ]; then
  echo "ERROR: document root not found: $DEPLOYPATH" >&2
  exit 1
fi

# Stage assets/ beside the live copy, then swap it in. The old directory is
# only removed once the new one is complete, so a failed or interrupted copy
# can never leave the site without its stylesheet and images.
STAGE="$DEPLOYPATH/.assets-incoming"
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -r "$SRC/assets/." "$STAGE/"

rm -rf "$DEPLOYPATH/assets"
mv "$STAGE" "$DEPLOYPATH/assets"

# Everything else is copied in place and never deleted, which is what keeps
# cgi-bin, php.ini, .user.ini, .well-known and .htaccess safe.
cp "$SRC/index.html" "$SRC/robots.txt" "$SRC/sitemap.xml" "$DEPLOYPATH/"

echo "Deployed $(git -C "$SRC" rev-parse --short HEAD 2>/dev/null || echo '?') to $DEPLOYPATH"
