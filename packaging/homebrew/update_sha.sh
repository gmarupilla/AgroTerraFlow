#!/usr/bin/env bash
# Usage: ./update_sha.sh <version>
# Example: ./update_sha.sh 0.2.1
set -euo pipefail

VERSION="${1:?Usage: $0 <version>}"
URL="https://github.com/gmarupilla/AgroTerraFlow/archive/refs/tags/v${VERSION}.tar.gz"
SHA=$(curl -sL "$URL" | shasum -a 256 | awk '{print $1}')

FORMULA="$(dirname "$0")/Formula/terraflow.rb"

# Cross-platform sed: GNU (Linux) uses -i without arg; BSD (macOS) requires -i ''
if sed --version 2>/dev/null | grep -q GNU; then
  sed -i "s|sha256 \"[^\"]*\"|sha256 \"${SHA}\"|" "$FORMULA"
  sed -i "s|archive/refs/tags/v[0-9.]*\.tar\.gz|archive/refs/tags/v${VERSION}.tar.gz|" "$FORMULA"
else
  sed -i '' "s|sha256 \"[^\"]*\"|sha256 \"${SHA}\"|" "$FORMULA"
  sed -i '' "s|archive/refs/tags/v[0-9.]*\.tar\.gz|archive/refs/tags/v${VERSION}.tar.gz|" "$FORMULA"
fi

echo "Updated $FORMULA with sha256 $SHA for v${VERSION}"
