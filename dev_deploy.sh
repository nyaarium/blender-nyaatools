#!/bin/bash
#
# Deploy NyaaTools to Blender addons folder.
#
# Configuration:
#   Create a .env file with DEPLOY_PATH set to your Blender addons folder.
#   Example .env:
#     DEPLOY_PATH="/mnt/c/Users/YourName/AppData/Roaming/Blender Foundation/Blender/5.0/scripts/addons/NyaaTools"
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$SCRIPT_DIR/NyaaTools"

# Load config from .env if it exists
if [ -f "$SCRIPT_DIR/.env" ]; then
    source "$SCRIPT_DIR/.env"
fi

# Check if DEPLOY_PATH is set
if [ -z "$DEPLOY_PATH" ]; then
    echo "Error: DEPLOY_PATH not set."
    echo ""
    echo "Create a .env file with:"
    echo '  DEPLOY_PATH="/mnt/c/Users/YourName/AppData/Roaming/Blender Foundation/Blender/5.0/scripts/addons/NyaaTools"'
    exit 1
fi

# Verify source exists
if [ ! -d "$SOURCE_DIR" ]; then
    echo "Error: Source directory not found: $SOURCE_DIR"
    exit 1
fi

# Create destination if it doesn't exist
mkdir -p "$DEPLOY_PATH"

# Remove Python bytecode caches from destination so rsync --delete can remove renamed folders
find "$DEPLOY_PATH" -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
find "$DEPLOY_PATH" -type f -name "*.pyc" -delete 2>/dev/null || true
find "$DEPLOY_PATH" -type f -name "*.pyo" -delete 2>/dev/null || true

# Sync files (excludes __pycache__ and .pyc files)
echo "Deploying NyaaTools..."
echo "  From: $SOURCE_DIR"
echo "  To:   $DEPLOY_PATH"
echo ""

rsync -av --delete \
    --exclude="__pycache__" \
    --exclude="*.pyc" \
    --exclude="*.pyo" \
    "$SOURCE_DIR/" "$DEPLOY_PATH/"

echo ""
echo "Done! In Blender: Disable/Enable the addon to reload changes."

