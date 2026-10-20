#!/bin/bash

# Local Photo Search - Automation Script
# Provides convenient commands for downloading, indexing, and serving photos
# with photo management and status reporting capabilities

set -e  # Exit on error

# Always run from the project root regardless of where the script is called from
cd "$(dirname "$0")"

# Color codes for status messages
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'  # No Color

# Configuration
SAMPLE_PHOTOS_DIR="sample-photos"
DATA_DIR="data"
DEFAULT_PORT=8000
DEFAULT_PHOTO_COUNT=400

# Utility functions
print_status() {
    echo -e "${BLUE}▶${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_step() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Check if uv is installed
check_uv() {
    if ! command -v uv &> /dev/null; then
        print_error "uv is not installed. Please install it from https://docs.astral.sh/uv/"
        exit 1
    fi
    print_success "uv found"
}

# Install dependencies
install_deps() {
    print_step "Installing Python dependencies"
    print_status "Running 'uv sync'..."
    uv sync
    print_success "Dependencies installed"
}

# Download sample photos
download_photos() {
    local count=${1:-$DEFAULT_PHOTO_COUNT}

    print_step "Downloading sample photos"
    print_status "Downloading $count photos from Unsplash..."

    if uv run scripts/download_sample_photos.py "$count"; then
        local actual_count=$(ls -1 "$SAMPLE_PHOTOS_DIR"/*.jpg 2>/dev/null | wc -l || echo 0)
        print_success "Downloaded $actual_count photos to $SAMPLE_PHOTOS_DIR/"
    else
        print_error "Failed to download sample photos"
        exit 1
    fi
}

# Index photos
index_photos() {
    local photo_folder=${1:-$SAMPLE_PHOTOS_DIR}

    if [ ! -d "$photo_folder" ]; then
        print_error "Photo folder not found: $photo_folder"
        exit 1
    fi

    print_step "Indexing photos"
    print_status "Indexing photos from: $photo_folder"
    print_status "This may take a few minutes on first run (model downloads ~1.5 GB)..."
    echo ""

    if uv run photosearch --data "$DATA_DIR" index "$photo_folder"; then
        print_success "Photos indexed successfully"
    else
        print_error "Failed to index photos"
        exit 1
    fi
}

# Start web server
start_server() {
    local port=${1:-$DEFAULT_PORT}

    print_step "Starting web server"
    print_success "Server starting..."
    echo ""
    echo -e "${GREEN}╭─────────────────────────────────────────────────────────────╮${NC}"
    echo -e "${GREEN}│                                                             │${NC}"
    echo -e "${GREEN}│  Open your browser to: ${BLUE}http://127.0.0.1:$port${GREEN}             │${NC}"
    echo -e "${GREEN}│                                                             │${NC}"
    echo -e "${GREEN}│  Search, view similar photos, or drag images to search!   │${NC}"
    echo -e "${GREEN}│                                                             │${NC}"
    echo -e "${GREEN}│  Press Ctrl+C to stop the server                           │${NC}"
    echo -e "${GREEN}│                                                             │${NC}"
    echo -e "${GREEN}╰─────────────────────────────────────────────────────────────╯${NC}"
    echo ""

    uv run photosearch --data "$DATA_DIR" serve --port "$port"
}

# Clean up samples and database
clean() {
    print_step "Cleaning up"

    if [ -d "$SAMPLE_PHOTOS_DIR" ]; then
        print_status "Deleting sample photos directory: $SAMPLE_PHOTOS_DIR"
        rm -rf "$SAMPLE_PHOTOS_DIR"
        print_success "Sample photos deleted"
    fi

    if [ -f "$DATA_DIR/photos.db" ]; then
        print_status "Deleting database: $DATA_DIR/photos.db"
        rm -f "$DATA_DIR/photos.db"
        print_success "Database deleted"
    fi

    if [ -d "$DATA_DIR/thumbs" ]; then
        print_status "Deleting thumbnails directory: $DATA_DIR/thumbs"
        rm -rf "$DATA_DIR/thumbs"
        print_success "Thumbnails deleted"
    fi

    print_success "Cleanup complete"
}

# Quick test: compare text with images
try_command() {
    if [ $# -lt 2 ]; then
        print_error "Usage: $0 try <query> <photo1> [photo2] ..."
        echo "Example: $0 try 'a dog on the beach' sample-photos/unsplash-237.jpg sample-photos/unsplash-10.jpg"
        exit 1
    fi

    local query="$1"
    shift
    local photos=("$@")

    print_step "Quick test: embedding comparison"
    print_status "Query: \"$query\""
    print_status "Comparing with ${#photos[@]} photo(s)..."
    echo ""

    uv run photosearch try "$query" "${photos[@]}"
}

# Display help
show_help() {
    cat << EOF
${BLUE}Local Photo Search - Automation Script${NC}

${YELLOW}Usage:${NC}
  $0 [command] [options]

${YELLOW}Commands:${NC}
  ${GREEN}setup${NC}              Download samples, install deps, index, and start server
  ${GREEN}download${NC} [N]       Download N sample photos (default: $DEFAULT_PHOTO_COUNT)
  ${GREEN}index${NC} <folder>     Index photos from a folder
  ${GREEN}serve${NC} [PORT]       Start web server (default port: $DEFAULT_PORT)
  ${GREEN}try${NC} <query> <photos>...
                  Quick test: compare text with images without database
  ${GREEN}clean${NC}              Delete sample photos and database, then re-download
  ${GREEN}help${NC}               Show this help message

${YELLOW}Examples:${NC}
  # Complete setup and start server
  $0 setup

  # Download more photos
  $0 download 500

  # Index your own photo folder
  $0 index ~/Pictures

  # Start server on a different port
  $0 serve 8080

  # Quick test without database
  $0 try "a dog on the beach" sample-photos/unsplash-237.jpg sample-photos/unsplash-10.jpg

  # Clean up and start fresh
  $0 clean
  $0 setup

${YELLOW}Notes:${NC}
  - On first run, the embedding model (~1.5 GB) will be downloaded automatically
  - Indexing only processes new photos; already indexed photos are skipped
  - For detailed API documentation, run: uv run photosearch serve --help

EOF
}

# Main command dispatcher
main() {
    # Check prerequisites
    check_uv

    # Handle no arguments
    if [ $# -eq 0 ]; then
        show_help
        exit 0
    fi

    local command="$1"
    shift  # Remove command from arguments

    case "$command" in
        setup)
            print_status "Starting complete setup..."
            install_deps
            download_photos
            index_photos
            print_step "Ready to use!"
            print_success "Everything is ready. Starting server..."
            start_server "${1:-$DEFAULT_PORT}"
            ;;
        download)
            install_deps
            download_photos "${1:-$DEFAULT_PHOTO_COUNT}"
            ;;
        index)
            if [ -z "$1" ]; then
                print_error "Please specify a photo folder"
                echo "Usage: $0 index <folder>"
                exit 1
            fi
            install_deps
            index_photos "$1"
            ;;
        serve)
            start_server "${1:-$DEFAULT_PORT}"
            ;;
        try)
            install_deps
            try_command "$@"
            ;;
        clean)
            clean
            print_status "Re-downloading sample photos..."
            download_photos
            print_success "Ready to index with: $0 index $SAMPLE_PHOTOS_DIR"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "Unknown command: $command"
            echo "Run '$0 help' for usage information"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
