# TradeRunner - Enhanced Trading Strategy Framework

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/release/python-3100/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

> **Scalable n-strategy architecture for algorithmic trading with unified interfaces, comprehensive testing, and dashboard integration.**

## 🎯 **Overview**

TradeRunner is an enhanced trading strategy framework designed to scale from single strategies to n-strategy implementations. Built with modern Python practices, it provides:

- **🏗️ Scalable Architecture**: Protocol-based design for easy strategy expansion
- **📊 Unified Signal Format**: Standardized signal interface across all strategies  
- **🔧 Configuration Management**: Pydantic-based validation and schema generation
- **🖥️ Dashboard Integration**: Streamlit-based monitoring and control interface
- **🧪 Comprehensive Testing**: Quality-first development with automated checks

## 🚀 **Quick Start**

### **Installation**

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/traderunner.git
cd traderunner

# Setup virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt

# Verify installation
PYTHONPATH=src python -c "from strategies import *; print('✅ TradeRunner ready!')"
```

### **Basic Usage**

```python
from strategies.base import Signal, StrategyConfig

# Create a trading signal
signal = Signal(
    timestamp="2025-01-01T10:00:00",
    symbol="AAPL",
    signal_type="LONG",
    strategy="inside_bar",
