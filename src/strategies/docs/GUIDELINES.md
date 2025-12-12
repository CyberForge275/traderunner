# Strategy Documentation Guidelines

## Purpose

Each strategy should have a `docs/` folder containing comprehensive documentation about:
- Strategy logic and entry/exit criteria
- Risk management rules
- Configuration parameters
- Test results and performance metrics
- Known limitations and improvement ideas

## Required Files

### README.md (Required)
Main strategy documentation covering:
- Overview and description
- Entry/exit logic
- Risk management (stop loss, take profit, position sizing)
- Session filtering rules
- Configuration parameters
- File structure
- Testing instructions
- Performance metrics
- Known limitations
- Improvement backlog
- Version history

### Optional Documents

- **PERFORMANCE.md**: Detailed backtest results, metrics, trade logs
- **RESEARCH.md**: Strategy research, hypothesis, validation
- **CHANGELOG.md**: Detailed version history
- **EXAMPLES.md**: Example trades with screenshots
- **TROUBLESHOOTING.md**: Common issues and solutions

## Template

See [`inside_bar/docs/README.md`](inside_bar/docs/README.md) for a complete example.

## Maintenance

- Update after significant changes
- Document all new versions
- Keep performance metrics current
- Track improvements and limitations

---

*Last updated: 2025-12-11*
