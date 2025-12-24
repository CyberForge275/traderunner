from __future__ import annotations

from pathlib import Path
from dash import Input, Output, State, html, dcc, no_update
import dash_bootstrap_components as dbc

from trading_dashboard.repositories.trade_repository import TradeRepository
from trading_dashboard.services.trade_detail_service import TradeDetailService
from trading_dashboard.plots.trade_inspector_plot import build_trade_chart


ARTIFACTS_ROOT = Path("artifacts/backtests")


def _list_runs() -> list[dict]:
    if not ARTIFACTS_ROOT.exists():
        return []

    def _started_at(p: Path) -> float:
        meta = p / "run_meta.json"
        if meta.exists():
            try:
                import json
                data = json.loads(meta.read_text())
                ts = data.get("started_at") or data.get("started_at_utc")
                if ts:
                    return pd.to_datetime(ts, utc=True, errors="coerce").timestamp()
            except Exception:
                pass
        return p.stat().st_mtime

    candidates = []
    for path in ARTIFACTS_ROOT.iterdir():
        if not path.is_dir():
            continue
        if (path / "trades.csv").exists():
            candidates.append((path, _started_at(path)))

    candidates.sort(key=lambda x: x[1], reverse=True)
    return [{"label": p.name, "value": p.name} for p, _ in candidates]


def register_trade_inspector_callbacks(app):
    repo = TradeRepository(artifacts_root=ARTIFACTS_ROOT)
    service = TradeDetailService(repo)

    @app.callback(
        Output("ti-run-dropdown", "options"),
        Input("main-tabs", "active_tab"),
    )
    def _load_runs(active_tab):
        if active_tab != "trade-inspector":
            return no_update
        return _list_runs()

    @app.callback(
        Output("ti-trade-dropdown", "options"),
        Input("ti-run-dropdown", "value"),
    )
    def _load_trades(run_id):
        if not run_id:
            return []
        trades = repo.load_trades(run_id)
        if trades is None or trades.empty:
            return []
        options = []
        for idx, row in trades.iterrows():
            label = f"#{idx} {row.get('symbol', '')} {row.get('entry_ts', '')} {row.get('side', '')} PnL={row.get('pnl', '')}"
            options.append({"label": label, "value": idx})
        return options

    @app.callback(
        Output("ti-trade-chart", "figure"),
        Output("ti-trade-summary", "children"),
        Output("ti-evidence-status", "children"),
        Output("ti-resize-request", "data"),
        Input("ti-run-dropdown", "value"),
        Input("ti-trade-dropdown", "value"),
        State("ti-resize-request", "data"),
    )
    def _update_trade(run_id, trade_id, resize_state):
        if resize_state is None:
            resize_state = {"req": 0}

        if not run_id or trade_id is None:
            return {}, html.Div("Select a run and trade"), "", resize_state

        detail = service.get_trade_detail(run_id, int(trade_id))
        if detail is None:
            return {}, html.Div("Trade not found"), "", resize_state

        fig = build_trade_chart(detail.trade_row, detail.exec_bars)
        summary = dbc.Card(
            dbc.CardBody(
                [
                    html.Div(f"Run: {run_id}"),
                    html.Div(f"Trade ID: {trade_id}"),
                    html.Div(f"Symbol: {detail.trade_row.get('symbol', '')}"),
                    html.Div(f"Side: {detail.trade_row.get('side', '')}"),
                    html.Div(f"PNL: {detail.trade_row.get('pnl', '')}"),
                ]
            )
        )

        evidence_status = ""
        if detail.evidence_row is not None:
            ev = detail.evidence_row
            badge = "✅ PROVEN" if ev.get("proof_status") == "PROVEN" else ("⚠️ PARTIAL" if ev.get("proof_status") == "PARTIAL" else "⚠️ NO_PROOF")
            evidence_status = dbc.Alert(
                [
                    html.Strong(badge),
                    html.Div(f"Entry proven: {ev.get('entry_exec_proven')} | Exit proven: {ev.get('exit_exec_proven')} | RTH: {ev.get('rth_compliant')}"),
                ],
                color="success" if ev.get("proof_status") == "PROVEN" else "warning",
            )

        new_req = {"req": int(resize_state.get("req", 0)) + 1}
        return fig, summary, evidence_status, new_req

    # One-shot clientside resize per selection
    app.clientside_callback(
        """
        function(fig, req, ack) {
            if (!fig || !fig.data) { return ack || {req_seen: 0}; }
            const currentReq = (req && req.req) ? req.req : 0;
            const seen = (ack && ack.req_seen) ? ack.req_seen : 0;
            if (currentReq === seen) { return ack || {req_seen: seen}; }
            const gd = document.getElementById('ti-trade-chart');
            if (gd && window.Plotly && gd.data) {
                try { window.Plotly.Plots.resize(gd); } catch(e) { /* ignore */ }
            }
            return {req_seen: currentReq};
        }
        """,
        Output("ti-resize-ack", "data"),
        Input("ti-trade-chart", "figure"),
        Input("ti-resize-request", "data"),
        State("ti-resize-ack", "data"),
    )
