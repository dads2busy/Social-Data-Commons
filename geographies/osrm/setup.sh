#!/usr/bin/env bash
# Download OSM data for 8 states, merge, and prepare for OSRM routing.
# Run once — then use `docker compose up -d` to start the server.
#
# Prerequisites: brew install osmium-tool wget
# Disk space: ~15 GB (PBFs + OSRM preprocessed files)
# Time: ~30-45 min (download + preprocessing)

set -euo pipefail
cd "$(dirname "$0")"

DATA_DIR="./data"
mkdir -p "$DATA_DIR"

STATES=(
    virginia
    maryland
    district-of-columbia
    delaware
    west-virginia
    north-carolina
    tennessee
    kentucky
)

# Step 1: Download state PBF extracts
echo "=== Downloading OSM extracts ==="
for st in "${STATES[@]}"; do
    file="$DATA_DIR/${st}-latest.osm.pbf"
    if [ -f "$file" ]; then
        echo "  $st — already downloaded"
    else
        echo "  $st — downloading..."
        wget -q --show-progress -O "$file" \
            "https://download.geofabrik.de/north-america/us/${st}-latest.osm.pbf"
    fi
done

# Step 2: Merge into single PBF
MERGED="$DATA_DIR/8states.osm.pbf"
if [ -f "$MERGED" ]; then
    echo "=== Merged file already exists, skipping merge ==="
else
    echo "=== Merging 8 state extracts ==="
    osmium merge "$DATA_DIR"/*-latest.osm.pbf -o "$MERGED"
fi

# Step 3: OSRM preprocessing (extract → partition → customize)
OSRM_IMAGE="ghcr.io/project-osrm/osrm-backend"

if [ -f "$DATA_DIR/8states.osrm.cell_metrics" ]; then
    echo "=== OSRM data already preprocessed ==="
else
    echo "=== OSRM extract (this takes ~15-20 min) ==="
    docker run -t --rm -v "${PWD}/data:/data" "$OSRM_IMAGE" \
        osrm-extract -p /opt/car.lua /data/8states.osm.pbf

    echo "=== OSRM partition ==="
    docker run -t --rm -v "${PWD}/data:/data" "$OSRM_IMAGE" \
        osrm-partition /data/8states.osrm

    echo "=== OSRM customize ==="
    docker run -t --rm -v "${PWD}/data:/data" "$OSRM_IMAGE" \
        osrm-customize /data/8states.osrm
fi

echo ""
echo "=== Setup complete! ==="
echo "Start the server with:  cd geographies/osrm && docker compose up -d"
echo "Stop the server with:   docker compose down"
echo ""
echo "Then run:  uv run python geographies/osrm/build_travel_time_matrix.py"
