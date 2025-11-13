# TradeRunner - Factory Context

## Runtime

- Python: 3.12

- Create venv: python -m venv .venv && source .venv/bin/activate

- Install: pip install -r requirements.txt

## Commands (traderunner)

- Ensure OHLCV: PYTHONPATH=src .venv/bin/python -m data.cli_ensure_ohlcv --symbols AAPL,MSFT,TSLA,IREN --start 2025-07-31 --end 2025-10-29 --exchange US --artifacts-dir artifacts

- Signals (M5): PYTHONPATH=src .venv/bin/python -m signals.cli_inside_bar --data-path artifacts/data_m5 --tz Europe/Berlin --symbols AAPL,MSFT,TSLA,IREN --sessions "15:00-16:00,16:00-17:00" --trade-type BOTH --ib-mode inclusive --min-master-body 0.5 --atr-period 14 --atr-method RMA --atr-filter-mode multiplier --max-master-atr-mult 1.0 --rrr 1.0 --sl-cap 80 --sl-cap-units points --exec-lag 0

- Export Orders: PYTHONPATH=src .venv/bin/python -m trade.cli_export_orders --source artifacts/signals/current_signals_ib.csv --sessions 15:00-16:00,16:00-17:00 --sizing risk --equity 10000 --risk-pct 1.0 --tick-size 0.01 --round-mode nearest --tif DAY

## Secrets

- Do not commit real tokens. Use credentials.example.toml. Real values come from env vars or local credentials.toml excluded by .gitignore.

## Data

- Optional small sample under artifacts/ for fast validation. Avoid network fetches in automated runs.

## Ignore

- .venv/, __pycache__/, artifacts/** (large), *.ipynb_checkpoints/
