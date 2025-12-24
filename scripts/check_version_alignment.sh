#!/bin/bash
# check_version_alignment.sh - Verify version alignment between repos
#
# Usage: ./check_version_alignment.sh <strategy>
# Example: ./check_version_alignment.sh inside_bar
#
# Checks that the version declared in traderunner/core.py matches
# the vendored version in marketdata-stream

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check argument
if [ -z "$1" ]; then
    echo "Usage: $0 <strategy>"
    echo "Example: $0 inside_bar"
    exit 1
fi

STRATEGY=$1

echo -e "${YELLOW}🔍 Checking version alignment for ${STRATEGY}...${NC}"

# Paths
TR_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MD_ROOT="${TR_ROOT}/../marketdata-stream"

# Extract traderunner version
TR_CORE="${TR_ROOT}/src/strategies/${STRATEGY}/core.py"
if [ ! -f "$TR_CORE" ]; then
    echo -e "${RED}❌ Core not found: ${TR_CORE}${NC}"
    exit 1
fi

TR_VERSION=$(grep '^__version__ = ' "$TR_CORE" | cut -d'"' -f2)

# Extract marketdata-stream vendored version
MD_VERSION_FILE="${MD_ROOT}/src/unified_core/version.py"
if [ ! -f "$MD_VERSION_FILE" ]; then
    echo -e "${YELLOW}⚠️  Version marker not found: ${MD_VERSION_FILE}${NC}"
    echo "   This might be the first vendoring, or version.py wasn't created."
    exit 0
fi

MD_VERSION=$(grep '^VENDORED_VERSION = ' "$MD_VERSION_FILE" | cut -d'"' -f2)

# Compare versions
echo ""
echo "Version comparison:"
echo "  traderunner (source):     ${TR_VERSION}"
echo "  marketdata-stream (vendor): ${MD_VERSION}"
echo ""

if [ "$TR_VERSION" != "$MD_VERSION" ]; then
    echo -e "${RED}❌ Version mismatch!${NC}"
    echo ""
    echo "The vendored strategy in marketdata-stream is out of sync."
    echo ""
    echo "To fix:"
    echo "  ./scripts/vendor_strategy.sh ${STRATEGY} ${TR_VERSION}"
    exit 1
else
    echo -e "${GREEN}✅ Versions aligned: ${TR_VERSION}${NC}"

    # Checksum verification for multi-version support
    MD_VERSION_CLEAN=$(echo "$MD_VERSION" | sed 's/\./_/g')
    MD_CORE_FILE="${MD_ROOT}/src/unified_core/${STRATEGY}_core_v${MD_VERSION_CLEAN}.py"

    # Fallback for legacy (non-versioned) file
    if [ ! -f "$MD_CORE_FILE" ]; then
         MD_CORE_FILE="${MD_ROOT}/src/unified_core/core.py"
    fi

    if [ ! -f "$MD_CORE_FILE" ]; then
        echo -e "${YELLOW}⚠️  Core file not found at: ${MD_CORE_FILE}${NC}"
        echo "   Cannot verify checksum."
        exit 1
    fi

    TR_CHECKSUM=$(sha256sum "$TR_CORE" | awk '{print $1}' | cut -c1-16)
    MD_CHECKSUM=$(sha256sum "$MD_CORE_FILE" | awk '{print $1}' | cut -c1-16)

    echo ""
    echo "Checksum verification:"
    echo "  traderunner:       ${TR_CHECKSUM}"
    echo "  marketdata-stream: ${MD_CHECKSUM} ($(basename "$MD_CORE_FILE"))"

    if [ "$TR_CHECKSUM" != "$MD_CHECKSUM" ]; then
        echo -e "${YELLOW}⚠️  Checksums differ!${NC}"
        echo "   Versions match but file contents differ."
        echo "   Consider re-vendoring to ensure perfect sync."
        exit 1
    else
        echo -e "${GREEN}✅ Checksums match${NC}"
    fi
fi
