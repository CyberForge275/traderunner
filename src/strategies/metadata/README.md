# Strategy Metadata Package

## Overview

**Single Source of Truth** for all trading strategy metadata.

This package provides enterprise-grade schema for strategy definitions that ALL systems must use.

## ✅ Story 1.1: COMPLETE

**Deliverables**:
- [x] `StrategyMetadata` dataclass with full schema
- [x] `StrategyCapabilities` for feature flags
- [x] `DataRequirements` for data dependencies
- [x] `DeploymentInfo` for tracking deployments
- [x] Complete validation (IDs, versions, timeframes)
- [x] Serialization (to_dict/from_dict)
- [x] 17 unit tests (100% pass rate)

**Test Coverage**: 17/17 tests passing ✅

## Usage

```python
from strategies.metadata import StrategyMetadata, StrategyCapabilities, DataRequirements

# Create metadata
metadata = StrategyMetadata(
    strategy_id="inside_bar_v2",
    canonical_name="inside_bar",
    display_name="Inside Bar Breakout",
    version="2.0.0",
    description="Inside bar pattern with ATR-based breakouts",
    
    capabilities=StrategyCapabilities(
        supports_live_trading=True,
        supports_backtest=True,
        supports_pre_papertrade=True,
    ),
    
    data_requirements=DataRequirements(
        required_timeframes=["M5"],
        min_history_days=30,
    ),
    
    config_class_path="strategies.inside_bar.core.InsideBarConfig",
    default_parameters={"atr_period": 14, "risk_reward_ratio": 2.0},
    signal_module_path="signals.cli_inside_bar",
    core_module_path="strategies.inside_bar.core",
)

# Validate automatically on creation
metadata.validate()  # Called in __post_init__

# Serialize
data_dict = metadata.to_dict()

# Deserialize
restored = StrategyMetadata.from_dict(data_dict)

# Check environment compatibility
if metadata.is_compatible_with_environment(DeploymentEnvironment.LIVE_TRADING):
    print("Ready for live trading!")
```

## Schema

### StrategyMetadata

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `strategy_id` | str | ✅ | Unique ID (e.g., `"inside_bar_v2"`) |
| `canonical_name` | str | ✅ | Base name (e.g., `"inside_bar"`) |
| `display_name` | str | ✅ | Human name (e.g., `"Inside Bar Breakout"`) |
| `version` | str | ✅ | Semver (e.g., `"2.0.0"`) |
| `description` | str | ✅ | Strategy description |
| `capabilities` | StrategyCapabilities | ✅ | What it can do |
| `data_requirements` | DataRequirements | ✅ | What data it needs |
| `config_class_path` | str | ✅ | Config class path |
| `default_parameters` | Dict | ✅ | Default params |
| `signal_module_path` | str | ✅ | Signal generator path |
| `core_module_path` | str | ✅ | Core implementation path |
| `parameter_schema` | Dict | ❌ | JSON Schema for validation |
| `required_indicators` | List[str] | ❌ | Required indicators |
| `deployment_info` | DeploymentInfo | ❌ | Deployment tracking |
| `created_at` | datetime | Auto | Creation time |
| `updated_at` | datetime | Auto | Last update time |
| `created_by` | str | Auto | Creator (default: "system") |
| `documentation_url` | str | ❌ | Docs URL |

### Validation Rules

**strategy_id**:
- Alphanumeric + underscores/hyphens only
- No spaces or special characters

**Version**:
- Must be semver (e.g., "2.0.0")
- Three integer parts separated by dots

**Timeframes**:
- Must be one of: M1, M5, M15, M30, H1, H4, D1, W1

## Testing

```bash
# Run tests
pytest src/strategies/metadata/tests/ -v

# With coverage
pytest src/strategies/metadata/tests/ --cov=src/strategies/metadata
```

**Current Test Results**: ✅ 17/17 passing

## Next Steps

- [ ] Story 1.2: StrategyRegistry singleton
- [ ] Story 1.3: Strategy profiles (InsideBar, Rudometkin)
- [ ] Story 1.4: Database schema
- [ ] Story 1.5: Migrate Dashboard consumers
- [ ] Story 1.6: Migrate marketdata-stream
- [ ] Story 1.7: Architecture tests

## Architecture Decision

**Why dataclass instead of Pydantic?**
- Simpler, no external dependency
- Sufficient validation with custom `validate()`
- Better integration with existing code
- Can add Pydantic layer later if needed
