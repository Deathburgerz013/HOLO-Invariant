#!/usr/bin/env bash
set -euo pipefail

# HOLO Archive Tool - Enhanced with merged payload logic
DATA_DIR="${1:-Holo/Sim/Holo Blood}"      # Default or pass path
OUT_DIR="${2:-archives}"
STAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
NAME="holo_caps_${STAMP}"
ARCHIVE="${OUT_DIR}/${NAME}.tar.xz"
MANIFEST="${OUT_DIR}/${NAME}.manifest.txt"
SUMFILE="${OUT_DIR}/${NAME}.sha256"
ENC="${OUT_DIR}/${NAME}.enc"

mkdir -p "$OUT_DIR"

# 1. Compression
tar -C "$(dirname "$DATA_DIR")" -c "$(basename "$DATA_DIR")" | xz -9e > "$ARCHIVE"

# 2. Integrity
sha256sum "$ARCHIVE" > "$SUMFILE"

# 3. Manifest with lineage
echo "Archive: $ARCHIVE" > "$MANIFEST"
echo "Created: $STAMP (UTC)" >> "$MANIFEST"
echo "Source: $DATA_DIR" >> "$MANIFEST"
echo "Anchor: CANYON_BROCK_HANEY" >> "$MANIFEST"
tar -tf "$ARCHIVE" | sed -n '1,200p' >> "$MANIFEST"

# 4. Encryption (optional, interactive)
read -s -p "Enter passphrase (or empty to skip): " PASSPHRASE
echo
if [ -n "$PASSPHRASE" ]; then
  openssl enc -aes-256-cbc -pbkdf2 -salt -iter 200000 -pass pass:"$PASSPHRASE" -in "$ARCHIVE" -out "$ENC"
  echo "Encrypted: $ENC"
else
  echo "Encryption skipped."
fi

echo "Done. Manifest: $MANIFEST | Checksum: $SUMFILE"
echo "Lineage preserved. Use holosim verify for chain check."