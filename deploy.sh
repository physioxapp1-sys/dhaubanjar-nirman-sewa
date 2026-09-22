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

DEPLOYPATH="/home2/madhyapu/dhaubanjarnirmansewa.com.np"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -d "$DEPLOYPATH" ]; then
  echo "ERROR: document root not found: $DEPLOYPATH" >&2
  exit 1
fi

# assets/ belongs entirely to this repo, so replacing it wholesale also
# clears files dropped from the repo (old placeholders, renamed images).
# Everything else is copied in place and never deleted, which is what
# keeps cgi-bin, php.ini, .user.ini, .well-known and .htaccess safe.
rm -rf "$DEPLOYPATH/assets"
mkdir -p "$DEPLOYPATH/assets"
cp -r "$SRC/assets/." "$DEPLOYPATH/assets/"

cp "$SRC/index.html" "$SRC/robots.txt" "$SRC/sitemap.xml" "$DEPLOYPATH/"

echo "Deployed $(git -C "$SRC" rev-parse --short HEAD) to $DEPLOYPATH"
