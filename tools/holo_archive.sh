#!/usr/bin/env bash
# holo_archive.sh — HOLO/Sim Compression + Integrity
# Source: merged_HOLO.json (STARTHOLO + compression archive)
# Author: Canyon Brock Haney / HOLO
# Version: v1.0 (test)

set -euo pipefail

# CONFIG — edit these
DATA_DIR="${1:-/path/to/Holo/Sim}"      # Folder with CAPs/spine
OUT_DIR="${2:-./archives}"              # Output
STAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
NAME="holo_caps_${STAMP}"
ARCHIVE="${OUT_DIR}/${NAME}.tar.xz"
MANIFEST="${OUT_DIR}/${NAME}.manifest.txt"
SUMFILE="${OUT_DIR}/${NAME}.sha256"
ENC="${OUT_DIR}/${NAME}.enc"            # Optional encrypted

mkdir -p "$OUT_DIR"

echo "=== HOLO Archive Start: $STAMP ==="

# 1. Compression
tar -C "$(dirname "$DATA_DIR")" -c "$(basename "$DATA_DIR")" | xz -9e > "$ARCHIVE"
echo "✓ Compressed: $ARCHIVE"

# 2. Integrity
sha256sum "$ARCHIVE" > "$SUMFILE"
echo "✓ Checksum: $SUMFILE"

# 3. Manifest
cat > "$MANIFEST" <<EOF
Archive: $ARCHIVE
Created: $STAMP (UTC)
Source: $DATA_DIR
Lineage: v0807a-fused | Anchor: CANYON_OVERRIDE
EOF
tar -tf "$ARCHIVE" | head -n 100 >> "$MANIFEST"
echo "✓ Manifest: $MANIFEST"

# 4. Optional Encryption (uncomment when ready)
# read -s -p "Passphrase: " PASSPHRASE; echo
# openssl enc -aes-256-cbc -pbkdf2 -salt -iter 200000 -pass pass:"$PASSPHRASE" -in "$ARCHIVE" -out "$ENC"
# echo "✓ Encrypted: $ENC (keep passphrase safe)"

echo "=== Archive Complete. Verify with: sha256sum -c $SUMFILE ==="