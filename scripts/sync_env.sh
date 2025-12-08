#!/bin/bash
# Environment Sync Helper for traderunner project
# This script helps synchronize Python environments

set -e

PROJECT_DIR="/home/mirko/data/workspace/droid/traderunner"
PROJECT_VENV="$PROJECT_DIR/.venv"
SPYDER_VENV="/home/mirko/data/venv-spyder6"

echo "=========================================="
echo "TradeRunner Environment Sync Helper"
echo "=========================================="
echo ""

# Function to check if venv exists
check_venv() {
    if [ ! -d "$1" ]; then
        echo "❌ Virtual environment not found: $1"
        return 1
    fi
    echo "✅ Found: $1"
    return 0
}

# Function to install dependencies
install_deps() {
    local venv_path=$1
    echo ""
    echo "Installing dependencies in $venv_path..."
    source "$venv_path/bin/activate"
    
    # Install base requirements
    if [ -f "$PROJECT_DIR/requirements.txt" ]; then
        echo "  → Installing base requirements..."
        pip install -q -r "$PROJECT_DIR/requirements.txt"
    fi
    
    # Install dashboard requirements
    if [ -f "$PROJECT_DIR/trading_dashboard/requirements.txt" ]; then
        echo "  → Installing dashboard requirements..."
        pip install -q -r "$PROJECT_DIR/trading_dashboard/requirements.txt"
    fi
    
    deactivate
    echo "✅ Dependencies installed"
}

# Main menu
echo "Choose an option:"
echo "1) Sync project .venv with all requirements"
echo "2) Export spyder6 packages to file"
echo "3) Show package diff between environments"
echo "4) Verify project .venv installation"
echo ""
read -p "Enter choice [1-4]: " choice

case $choice in
    1)
        echo ""
        echo "Syncing project .venv..."
        check_venv "$PROJECT_VENV" || exit 1
        install_deps "$PROJECT_VENV"
        ;;
    2)
        echo ""
        echo "Exporting spyder6 packages..."
        check_venv "$SPYDER_VENV" || exit 1
        source "$SPYDER_VENV/bin/activate"
        pip list --format=freeze > "$PROJECT_DIR/spyder6_packages.txt"
        deactivate
        echo "✅ Exported to: $PROJECT_DIR/spyder6_packages.txt"
        ;;
    3)
        echo ""
        echo "Comparing environments..."
        check_venv "$PROJECT_VENV" || exit 1
        check_venv "$SPYDER_VENV" || exit 1
        
        # Get package lists
        source "$PROJECT_VENV/bin/activate"
        pip list --format=freeze | cut -d'=' -f1 | sort > /tmp/proj_pkgs.txt
        deactivate
        
        source "$SPYDER_VENV/bin/activate"
        pip list --format=freeze | cut -d'=' -f1 | sort > /tmp/spyder_pkgs.txt
        deactivate
        
        echo "Packages in spyder6 but NOT in project .venv:"
        comm -13 /tmp/proj_pkgs.txt /tmp/spyder_pkgs.txt | head -20
        echo ""
        echo "Packages in project .venv but NOT in spyder6:"
        comm -23 /tmp/proj_pkgs.txt /tmp/spyder_pkgs.txt | head -20
        ;;
    4)
        echo ""
        echo "Verifying project .venv installation..."
        check_venv "$PROJECT_VENV" || exit 1
        source "$PROJECT_VENV/bin/activate"
        python3 << 'PYEOF'
import sys
print("Python:", sys.version)
print("")
print("Critical packages:")
packages = ['pandas', 'numpy', 'pydantic', 'dash', 'plotly', 'streamlit', 'pyarrow']
for pkg in packages:
    try:
        mod = __import__(pkg)
        version = getattr(mod, '__version__', 'unknown')
        print(f"  ✅ {pkg}: {version}")
    except ImportError:
        print(f"  ❌ {pkg}: NOT INSTALLED")
PYEOF
        deactivate
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "=========================================="
echo "Done!"
echo "=========================================="
