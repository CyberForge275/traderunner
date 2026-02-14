"""Callback for editable SSOT strategy configuration in Backtests UI (draft/finalized workflow)."""

import logging
from dash import Input, Output, State, html, dcc, ALL, no_update
from dash.exceptions import PreventUpdate
from trading_dashboard.config_store.strategy_config_store import StrategyConfigStore
from trading_dashboard.ui_ids import SSOT

logger = logging.getLogger(__name__)


def _create_input_for_param(key, value, section, spec):
    """Create appropriate input component based on field spec."""
    input_id = SSOT.PARAM_INPUT(section, key)
    kind = spec.get("kind")
    
    label_style = {"fontSize": "0.85em", "marginTop": "4px"}
    
    if kind == "enum":
        options = spec.get("options", [])
        if key == "inside_bar_definition_mode":
            if "mb_high__ib_high_and_close_in_mb_range" not in options:
                options = list(options) + ["mb_high__ib_high_and_close_in_mb_range"]
        return html.Div([
            html.Label(key, style=label_style),
            dcc.Dropdown(
                id=input_id,
                options=[{"label": opt, "value": opt} for opt in options],
                value=value,
                clearable=False,
                style={
                    "width": "100%", 
                    "marginBottom": "8px"
                },
            ),
        ])
    elif kind == "bool" or (kind is None and isinstance(value, bool)):
        return html.Div([
            html.Label(key, style=label_style),
            dcc.Checklist(
                id=input_id,
                options=[{"label": "", "value": "true"}],
                value=["true"] if value else [],
                style={"marginBottom": "8px"},
            ),
        ])
    elif kind == "int" or (kind is None and isinstance(value, int)):
        return html.Div([
            html.Label(key, style=label_style),
            dcc.Input(
                id=input_id,
                type="number",
                value=value,
                step=1,
                style={"width": "100%", "marginBottom": "8px"},
            ),
        ])
    elif kind == "float" or (kind is None and isinstance(value, float)):
        return html.Div([
            html.Label(key, style=label_style),
            dcc.Input(
                id=input_id,
                type="text",
                value=str(value),
                style={"width": "100%", "marginBottom": "8px"},
            ),
        ])
    else:
        return html.Div([
            html.Label(key, style=label_style),
            dcc.Input(
                id=input_id,
                type="text",
                value=str(value),
                style={"width": "100%", "marginBottom": "8px"},
            ),
        ])


def register_ssot_config_viewer_callback(app):
    """Register callbacks for editable SSOT config viewer."""
    
    @app.callback(
        Output(SSOT.STRATEGY_ID, "options"),
        Input(SSOT.STRATEGY_ID, "id"),
    )
    def populate_strategy_dropdown(_):
        """Populate strategy dropdown from registry."""
        from src.strategies.config.registry import config_manager_registry
        
        strategies = config_manager_registry.list_strategies()
        if not strategies:
            return []
        
        return [{"label": sid, "value": sid} for sid in sorted(strategies)]
    
    @app.callback(
        Output(SSOT.VERSION, "options"),
        Input(SSOT.STRATEGY_ID, "value"),
    )
    def populate_version_dropdown(strategy_id):
        """Populate version dropdown based on selected strategy."""
        if not strategy_id:
            return []
        
        try:
            from src.strategies.config.registry import config_manager_registry
            manager = config_manager_registry.get_manager(strategy_id)
            if not manager:
                return []
            
            config = manager.load()
            versions = list(config.get("versions", {}).keys())
            sorted_versions = sorted(versions, reverse=True)
            
            return [{"label": v, "value": v} for v in sorted_versions]
        except Exception as e:
            logger.warning(f"Failed to load versions for {strategy_id}: {e}")
            return []
    
    @app.callback(
        [
            Output(SSOT.SAVE_VERSION_BUTTON, "disabled"),
            Output(SSOT.SAVE_VERSION_BUTTON, "children"),
            Output(SSOT.RESET_BUTTON, "disabled"),
            Output(SSOT.FINALIZE_BUTTON, "disabled"),
        ],
        [
            Input(SSOT.LOADED_DEFAULTS_STORE, "data"),
            Input(SSOT.NEW_VERSION, "value"),
        ]
    )
    def update_button_states(loaded_defaults, new_version):
        """Enable/disable buttons based on loaded config and finalized status."""
        
        if not loaded_defaults:
            # No config loaded: All buttons disabled
            return True, "Save", True, True
        
        is_finalized = loaded_defaults.get("strategy_finalized", False)
        has_new_version = bool(new_version and new_version.strip())
        
        # Save button logic
        if is_finalized and not has_new_version:
            save_disabled = True
            save_text = "Save as New Version (Required)"
        elif is_finalized and has_new_version:
            save_disabled = False
            save_text = f"Save as v{new_version.strip()}"
        else:  # Not finalized (draft mode)
            if has_new_version:
                save_disabled = False
                save_text = f"Save as v{new_version.strip()}"
            else:
                save_disabled = False
                save_text = "Save Changes"
        
        # Reset button: Enabled when config is loaded
        reset_disabled = False
        
        # Finalize button: Enabled when draft is loaded
        finalize_disabled = is_finalized
        
        return save_disabled, save_text, reset_disabled, finalize_disabled

    @app.callback(
        [
            Output(SSOT.LOAD_STATUS, "children"),
            Output(SSOT.LOADED_DEFAULTS_STORE, "data"),
            Output(SSOT.EDITABLE_FIELDS_CONTAINER, "children"),
        ],
        [
            Input(SSOT.LOAD_BUTTON, "n_clicks"),
            Input(SSOT.RESET_BUTTON, "n_clicks"),
        ],
        [
            State(SSOT.STRATEGY_ID, "value"),
            State(SSOT.VERSION, "value"),
            State(SSOT.LOADED_DEFAULTS_STORE, "data"),
        ],
        prevent_initial_call=True
    )
    def load_or_reset_config(load_clicks, reset_clicks, strategy_id, version, loaded_defaults):
        """Load config from SSOT or reset to loaded defaults."""
        from dash import callback_context
        
        if not callback_context.triggered:
            raise PreventUpdate
        
        trigger_id = callback_context.triggered[0]["prop_id"].split(".")[0]
        
        # Reset button
        if trigger_id == SSOT.RESET_BUTTON:
            if not loaded_defaults:
                raise PreventUpdate
            
            logger.info(f"actions: ui_config_reset strategy_id={loaded_defaults.get('strategy')} version={loaded_defaults.get('version')}")
            
            # Load specs
            specs = StrategyConfigStore.get_field_specs(loaded_defaults.get("strategy"))
            fields = _create_editable_fields(loaded_defaults, specs)
            
            status = html.Div([
                html.Span("🔄 ", style={"color": "#51cf66"}),
                html.Span("Reset to loaded defaults", style={"color": "#51cf66", "fontSize": "0.85em"}),
            ])
            
            return status, loaded_defaults, fields
        
        # Load button
        if not strategy_id or not version:
            status = html.Div("⚠️ Select strategy and version", style={"color": "#ff6b6b", "fontSize": "0.85em"})
            return status, None, []
        
        try:
            defaults = StrategyConfigStore.get_defaults(strategy_id.strip(), version.strip())
            
            core_params = defaults.get("core", {})
            tunable_params = defaults.get("tunable", {})
            is_finalized = defaults.get("strategy_finalized", False)
            if "max_position_loss_pct_equity" in core_params:
                val = core_params.get("max_position_loss_pct_equity")
                logger.info(
                    "actions: ui_loaded_default key=max_position_loss_pct_equity section=core val=%r type=%s strategy_id=%s version=%s",
                    val,
                    type(val).__name__,
                    strategy_id,
                    version,
                )
            if "max_position_loss_pct_equity" in tunable_params:
                val = tunable_params.get("max_position_loss_pct_equity")
                logger.info(
                    "actions: ui_loaded_default key=max_position_loss_pct_equity section=tunable val=%r type=%s strategy_id=%s version=%s",
                    val,
                    type(val).__name__,
                    strategy_id,
                    version,
                )
            
            logger.info(
                f"actions: ui_config_loaded strategy_id={strategy_id} version={version} "
                f"finalized={is_finalized} core_keys={len(core_params)} tunable_keys={len(tunable_params)}"
            )
            
            # Fetch specs
            specs = StrategyConfigStore.get_field_specs(strategy_id.strip())
            
            fields = _create_editable_fields(defaults, specs)
            
            finalized_label = " (finalized)" if is_finalized else " (draft)"
            status = html.Div([
                html.Span("✅ ", style={"color": "#51cf66"}),
                html.Span(f"Loaded {strategy_id} v{version}{finalized_label}", style={"color": "#51cf66", "fontSize": "0.85em"}),
            ])
            
            return status, defaults, fields
            
        except FileNotFoundError as e:
            logger.warning(f"actions: ui_load_config_failed exc=FileNotFoundError msg={str(e)}")
            status = html.Div([
                html.Span("❌ ", style={"color": "#ff6b6b"}),
                html.Span(f"File not found: {str(e)}", style={"color": "#ff6b6b", "fontSize": "0.85em"}),
            ])
            return status, None, []
        except ValueError as e:
            logger.warning(f"actions: ui_load_config_failed exc=ValueError msg={str(e)}")
            status = html.Div([
                html.Span("❌ ", style={"color": "#ff6b6b"}),
                html.Span(f"Error: {str(e)}", style={"color": "#ff6b6b", "fontSize": "0.85em"}),
            ])
            return status, None, []
        except Exception as e:
            logger.error(f"actions: ui_load_config_failed exc={type(e).__name__} msg={str(e)}")
            status = html.Div([
                html.Span("❌ ", style={"color": "#ff6b6b"}),
               html.Span(f"Error: {type(e).__name__}: {str(e)}", style={"color": "#ff6b6b", "fontSize": "0.85em"}),
            ])
            return status, None, []

    @app.callback(
        [
            Output(SSOT.SAVE_STATUS, "children"),
            Output(SSOT.VERSION, "value"),
            Output(SSOT.VERSION, "options", allow_duplicate=True),
            Output(SSOT.LOADED_DEFAULTS_STORE, "data", allow_duplicate=True),
            Output(SSOT.EDITABLE_FIELDS_CONTAINER, "children", allow_duplicate=True),
        ],
        [
            Input(SSOT.SAVE_VERSION_BUTTON, "n_clicks"),
        ],
        [
            State(SSOT.STRATEGY_ID, "value"),
            State(SSOT.VERSION, "value"),
            State(SSOT.NEW_VERSION, "value"),
            State(SSOT.LOADED_DEFAULTS_STORE, "data"),
            State(SSOT.PARAM_INPUT(ALL, ALL), "value"),
            State(SSOT.PARAM_INPUT(ALL, ALL), "id"),
        ],
        prevent_initial_call=True
    )
    def save_config(n_clicks, strategy_id, current_version, new_version, loaded_defaults, edited_values, edited_ids):
        """Save config: in-place for drafts, new version for finalized or if new_version provided."""
        from dash import callback_context
        logger.info("actions: ui_trigger %r", callback_context.triggered)

        if not n_clicks:
            raise PreventUpdate
        
        if not loaded_defaults:
            status = html.Div("❌ Load config first", style={"color": "#ff6b6b", "fontSize": "0.85em"})
            return status, no_update, no_update, no_update, no_update
        
        is_finalized = loaded_defaults.get("strategy_finalized", False)
        new_version_value = new_version.strip() if new_version else ""
        
        # Validation
        if is_finalized and not new_version_value:
            status = html.Div(
                "❌ Finalized versions require new version number",
                style={"color": "#ff6b6b", "fontSize": "0.85em"}
            )
            return status, no_update, no_update, no_update, no_update
        
        if new_version_value == current_version:
            status = html.Div(
                f"❌ New version must differ from current ({current_version})",
                style={"color": "#ff6b6b", "fontSize": "0.85em"}
            )
            return status, no_update, no_update, no_update, no_update
        
        try:
            # Compute overrides (must be inside try so validation errors return UI message, not HTTP 500)
            core_overrides, tunable_overrides = _compute_overrides(loaded_defaults, edited_values, edited_ids)

            if not new_version_value:
                # In-place update (draft only)
                StrategyConfigStore.update_existing_version(
                    strategy_id=strategy_id,
                    version=current_version,
                    core_overrides=core_overrides,
                    tunable_overrides=tunable_overrides
                )
                
                logger.info(
                    f"actions: ui_config_updated_inplace strategy_id={strategy_id} version={current_version} "
                    f"core_overrides={len(core_overrides)} tunable_overrides={len(tunable_overrides)}"
                )
                
                # Reload same version
                defaults_new = StrategyConfigStore.get_defaults(strategy_id, current_version)
                target_version = current_version
                success_msg = f"Saved changes to v{current_version}"
                
            else:
                # New version creation
                StrategyConfigStore.save_new_version(
                    strategy_id=strategy_id,
                    base_version=current_version,
                    new_version=new_version_value,
                    core_overrides=core_overrides,
                    tunable_overrides=tunable_overrides
                )
                
                logger.info(
                    f"actions: ui_config_version_saved strategy_id={strategy_id} "
                    f"base={current_version} new={new_version_value} "
                    f"core_overrides={len(core_overrides)} tunable_overrides={len(tunable_overrides)}"
                )
                
                # Reload new version
                defaults_new = StrategyConfigStore.get_defaults(strategy_id, new_version_value)
                target_version = new_version_value
                success_msg = f"Saved as v{new_version_value} and reloaded"
            
            logger.info(f"actions: ui_config_reloaded strategy_id={strategy_id} version={target_version}")
            
        except ValueError as e:
            logger.warning(f"actions: ui_save_failed exc=ValueError msg={str(e)}")
            status = html.Div([
                html.Span("❌ ", style={"color": "#ff6b6b"}),
                html.Span(str(e), style={"color": "#ff6b6b", "fontSize": "0.85em"}),
            ])
            return status, no_update, no_update, no_update, no_update
        except Exception as e:
            logger.error(f"actions: ui_save_failed exc={type(e).__name__} msg={str(e)}")
            status = html.Div([
                html.Span("❌ ", style={"color": "#ff6b6b"}),
                html.Span(f"Save failed: {str(e)}", style={"color": "#ff6b6b", "fontSize": "0.85em"}),
            ])
            return status, no_update, no_update, no_update, no_update
        
        # Update UI
        version_options = _get_version_options(strategy_id)
        specs = StrategyConfigStore.get_field_specs(strategy_id)
        fields = _create_editable_fields(defaults_new, specs)
        
        status = html.Div([
            html.Span("✅ ", style={"color": "#51cf66"}),
            html.Span(success_msg, style={"color": "#51cf66", "fontSize": "0.85em"}),
        ])
        
        return status, target_version, version_options, defaults_new, fields

    @app.callback(
        [
            Output(SSOT.SAVE_STATUS, "children", allow_duplicate=True),
            Output(SSOT.LOADED_DEFAULTS_STORE, "data", allow_duplicate=True),
            Output(SSOT.FINALIZE_BUTTON, "disabled", allow_duplicate=True),
        ],
        [Input(SSOT.FINALIZE_BUTTON, "n_clicks")],
        [
            State(SSOT.STRATEGY_ID, "value"),
            State(SSOT.VERSION, "value"),
            State(SSOT.LOADED_DEFAULTS_STORE, "data"),
        ],
        prevent_initial_call=True
    )
    def finalize_version(n_clicks, strategy_id, version, loaded_defaults):
        """Mark current version as finalized."""
        
        if not n_clicks or not loaded_defaults:
            raise PreventUpdate
        
        try:
            StrategyConfigStore.mark_as_finalized(strategy_id, version)
            
            # Reload to get updated finalized flag
            defaults_new = StrategyConfigStore.get_defaults(strategy_id, version)
            
            logger.info(f"actions: ui_config_finalized strategy_id={strategy_id} version={version}")
            
            status = html.Div([
                html.Span("✅ ", style={"color": "#51cf66"}),
                html.Span(f"Version {version} marked as finalized", style={"color": "#51cf66", "fontSize": "0.85em"}),
            ])
            
            return status, defaults_new, True
            
        except ValueError as e:
            logger.warning(f"actions: ui_finalize_failed exc=ValueError msg={str(e)}")
            status = html.Div([
                html.Span("❌ ", style={"color": "#ff6b6b"}),
                html.Span(str(e), style={"color": "#ff6b6b", "fontSize": "0.85em"}),
            ])
            return status, no_update, no_update
        except Exception as e:
            logger.error(f"actions: ui_finalize_failed exc={type(e).__name__} msg={str(e)}")
            status = html.Div([
                html.Span("❌ ", style={"color": "#ff6b6b"}),
                html.Span(f"Error: {str(e)}", style={"color": "#ff6b6b", "fontSize": "0.85em"}),
            ])
            return status, no_update, no_update


def _compute_overrides(loaded_defaults, edited_values, edited_ids):
    """Compute diff-only overrides from UI edits."""
    core_overrides = {}
    tunable_overrides = {}
    
    for value, id_dict in zip(edited_values, edited_ids):
        section = id_dict["section"]
        key = id_dict["key"]
        if key == "max_position_loss_pct_equity":
            logger.info(
                "actions: ui_param_raw key=max_position_loss_pct_equity value_repr=%r value_type=%s",
                value,
                type(value).__name__,
            )
        
        original = loaded_defaults[section][key]
        if key == "max_position_loss_pct_equity":
            logger.info(
                "actions: ui_param_orig key=max_position_loss_pct_equity orig=%r orig_type=%s",
                original,
                type(original).__name__,
            )
            if value in (None, ""):
                continue
            if isinstance(value, list):
                if not value:
                    continue
                value = value[0]
            if isinstance(value, str):
                value = value.strip()
                if value == "":
                    continue
                value = value.replace(",", ".")
            try:
                new_value = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Invalid max_position_loss_pct_equity value: {value!r}"
                ) from exc
            original_norm = float(original)
            if new_value != original_norm:
                if section == "core":
                    core_overrides[key] = new_value
                else:
                    tunable_overrides[key] = new_value
                logger.info(
                    "actions: ui_override_added key=%s new=%r orig=%r",
                    key,
                    new_value,
                    original_norm,
                )
            continue

        if key == "risk_reward_ratio":
            if value in (None, ""):
                continue
            if isinstance(value, list):
                if not value:
                    continue
                value = value[0]
            if isinstance(value, str):
                value = value.strip()
                if value == "":
                    continue
                value = value.replace(",", ".")
            try:
                new_value = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid float value for {key}: {value!r}") from exc
            if new_value != float(original):
                if section == "core":
                    core_overrides[key] = new_value
                else:
                    tunable_overrides[key] = new_value
            continue
        
        # Type conversion
        if isinstance(original, bool):
            new_value = (value == ["true"]) if isinstance(value, list) else bool(value)
        elif isinstance(original, int):
            if value in (None, ""):
                continue
            if isinstance(value, list):
                if not value:
                    continue
                value = value[0]
            if isinstance(value, str):
                value = value.strip()
                if value == "":
                    continue
                value = value.replace(",", ".")
            try:
                float_val = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid int value for {key}: {value!r}") from exc
            if not float_val.is_integer():
                raise ValueError(f"Invalid int value for {key}: {value!r}")
            new_value = int(float_val)
        elif isinstance(original, float):
            if value in (None, ""):
                continue
            if isinstance(value, list):
                if not value:
                    continue
                value = value[0]
            if isinstance(value, str):
                value = value.strip()
                if value == "":
                    continue
                value = value.replace(",", ".")
            new_value = float(value)
        elif isinstance(original, list):
            # Special handling for lists (e.g., session_filter)
            if isinstance(value, str):
                # Parse string input like "['09:30-11:00','14:00-15:00']" or "09:30-16:00"
                import ast
                try:
                    # Try to parse as Python literal (list)
                    new_value = ast.literal_eval(value)
                    if not isinstance(new_value, list):
                        new_value = [value]
                except (ValueError, SyntaxError):
                    # If parsing fails, treat as single string and wrap in list
                    new_value = [value] if value else []
            else:
                new_value = value if isinstance(value, list) else [value]
        else:
            new_value = str(value)
        
        # Only include if changed
        if new_value != original:
            if section == "core":
                core_overrides[key] = new_value
            else:
                tunable_overrides[key] = new_value
    
    return core_overrides, tunable_overrides


def _get_version_options(strategy_id):
    """Get version options from YAML (live read)."""
    try:
        from src.strategies.config.registry import config_manager_registry
        manager = config_manager_registry.get_manager(strategy_id)
        if not manager:
            return []
        
        config = manager.load()
        versions = list(config.get("versions", {}).keys())
        sorted_versions = sorted(versions, reverse=True)
        
        return [{"label": v, "value": v} for v in sorted_versions]
    except Exception:
        return []


def _create_editable_fields(defaults, specs):
    """Create editable input fields from defaults dict using field specs."""
    fields = []
    
    core_params = defaults.get("core", {})
    tunable_params = defaults.get("tunable", {})
    
    core_specs = specs.get("core", {})
    tunable_specs = specs.get("tunable", {})
    
    if core_params:
        fields.append(
            html.Div([
                html.Strong(
                    "Core Parameters:",
                    style={"color": "#51cf66", "marginTop": "12px", "marginBottom": "8px", "display": "block"}
                ),
                html.Div(
                    [_create_input_for_param(key, value, "core", core_specs.get(key, {})) for key, value in core_params.items()],
                    style={
                        "padding": "8px",
                        "backgroundColor": "rgba(255,255,255,0.02)",
                        "borderRadius": "4px",
                    }
                ),
            ])
        )
    
    if tunable_params:
        fields.append(
            html.Div([
                html.Strong(
                    "Tunable Parameters:",
                    style={"color": "#51cf66", "marginTop": "12px", "marginBottom": "8px", "display": "block"}
                ),
                html.Div(
                    [_create_input_for_param(key, value, "tunable", tunable_specs.get(key, {})) for key, value in tunable_params.items()],
                    style={
                        "padding": "8px",
                        "backgroundColor": "rgba(255,255,255,0.02)",
                        "borderRadius": "4px",
                    }
                ),
            ])
        )
    
    return fields
