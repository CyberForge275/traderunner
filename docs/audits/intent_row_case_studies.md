# Intent row case studies

## 260202_090827__HOOD_IB_maxLossPCT001_300d
### case 1: template_id=ib_HOOD_20250407_185500 symbol=HOOD signal_ts=2025-04-07 18:55:00+00:00
- suspicious fields: dbg_trigger_ts=2025-04-07 18:55:00+00:00, dbg_exit_ts_ny=2025-04-07 15:00:00-04:00, dbg_valid_to_ts_utc=2025-04-07 19:00:00+00:00, exit_ts=2025-04-07 19:00:00+00:00, exit_reason=session_end
- intent subset: {'template_id': 'ib_HOOD_20250407_185500', 'symbol': 'HOOD', 'signal_ts': '2025-04-07 18:55:00+00:00', 'side': 'SELL', 'entry_price': np.float64(34.56), 'stop_price': np.float64(34.96), 'take_profit_price': np.float64(33.760000000000005), 'exit_ts': '2025-04-07 19:00:00+00:00', 'exit_reason': 'session_end'}
- fills: [{'template_id': 'ib_HOOD_20250407_185500', 'fill_ts': '2025-04-07 18:55:00+00:00', 'fill_price': 34.66}, {'template_id': 'ib_HOOD_20250407_185500', 'fill_ts': '2025-04-07 19:00:00+00:00', 'fill_price': 34.96}]
- trade: [{'template_id': 'ib_HOOD_20250407_185500', 'entry_price': 34.66, 'exit_price': 34.96, 'pnl': -86.40000000000123}]

### case 2: template_id=ib_HOOD_20250407_185500 symbol=HOOD signal_ts=2025-04-07 18:55:00+00:00
- suspicious fields: dbg_trigger_ts=2025-04-07 18:55:00+00:00, dbg_exit_ts_ny=2025-04-07 15:00:00-04:00, dbg_valid_to_ts_utc=2025-04-07 19:00:00+00:00, exit_ts=2025-04-07 19:00:00+00:00, exit_reason=session_end
- intent subset: {'template_id': 'ib_HOOD_20250407_185500', 'symbol': 'HOOD', 'signal_ts': '2025-04-07 18:55:00+00:00', 'side': 'SELL', 'entry_price': np.float64(34.56), 'stop_price': np.float64(34.96), 'take_profit_price': np.float64(33.760000000000005), 'exit_ts': '2025-04-07 19:00:00+00:00', 'exit_reason': 'session_end'}
- fills: [{'template_id': 'ib_HOOD_20250407_185500', 'fill_ts': '2025-04-07 18:55:00+00:00', 'fill_price': 34.66}, {'template_id': 'ib_HOOD_20250407_185500', 'fill_ts': '2025-04-07 19:00:00+00:00', 'fill_price': 34.96}]
- trade: [{'template_id': 'ib_HOOD_20250407_185500', 'entry_price': 34.66, 'exit_price': 34.96, 'pnl': -86.40000000000123}]

### case 3: template_id=ib_HOOD_20250407_185500 symbol=HOOD signal_ts=2025-04-07 18:55:00+00:00
- suspicious fields: dbg_trigger_ts=2025-04-07 18:55:00+00:00, dbg_exit_ts_ny=2025-04-07 15:00:00-04:00, dbg_valid_to_ts_utc=2025-04-07 19:00:00+00:00, exit_ts=2025-04-07 19:00:00+00:00, exit_reason=session_end
- intent subset: {'template_id': 'ib_HOOD_20250407_185500', 'symbol': 'HOOD', 'signal_ts': '2025-04-07 18:55:00+00:00', 'side': 'SELL', 'entry_price': 34.56, 'stop_price': 34.96, 'take_profit_price': 33.760000000000005, 'exit_ts': '2025-04-07 19:00:00+00:00', 'exit_reason': 'session_end'}
- fills: [{'template_id': 'ib_HOOD_20250407_185500', 'fill_ts': '2025-04-07 18:55:00+00:00', 'fill_price': 34.66}, {'template_id': 'ib_HOOD_20250407_185500', 'fill_ts': '2025-04-07 19:00:00+00:00', 'fill_price': 34.96}]
- trade: [{'template_id': 'ib_HOOD_20250407_185500', 'entry_price': 34.66, 'exit_price': 34.96, 'pnl': -86.40000000000123}]

### case 4: template_id=ib_HOOD_20250408_134000 symbol=HOOD signal_ts=2025-04-08 13:40:00+00:00
- suspicious fields: dbg_trigger_ts=2025-04-08 13:40:00+00:00, dbg_exit_ts_ny=2025-04-08 11:00:00-04:00, dbg_valid_to_ts_utc=2025-04-08 15:00:00+00:00, exit_ts=2025-04-08 15:00:00+00:00, exit_reason=session_end
- intent subset: {'template_id': 'ib_HOOD_20250408_134000', 'symbol': 'HOOD', 'signal_ts': '2025-04-08 13:40:00+00:00', 'side': 'SELL', 'entry_price': 36.5, 'stop_price': 36.9, 'take_profit_price': 35.7, 'exit_ts': '2025-04-08 15:00:00+00:00', 'exit_reason': 'session_end'}
- fills: [{'template_id': 'ib_HOOD_20250408_134000', 'fill_ts': '2025-04-08 13:40:00+00:00', 'fill_price': 36.86}, {'template_id': 'ib_HOOD_20250408_134000', 'fill_ts': '2025-04-08 13:45:00+00:00', 'fill_price': 36.9}]
- trade: [{'template_id': 'ib_HOOD_20250408_134000', 'entry_price': 36.86, 'exit_price': 36.9, 'pnl': -10.719999999999771}]

### case 5: template_id=ib_HOOD_20250408_181500 symbol=HOOD signal_ts=2025-04-08 18:15:00+00:00
- suspicious fields: dbg_trigger_ts=2025-04-08 18:15:00+00:00, dbg_exit_ts_ny=2025-04-08 15:00:00-04:00, dbg_valid_to_ts_utc=2025-04-08 19:00:00+00:00, exit_ts=2025-04-08 19:00:00+00:00, exit_reason=session_end
- intent subset: {'template_id': 'ib_HOOD_20250408_181500', 'symbol': 'HOOD', 'signal_ts': '2025-04-08 18:15:00+00:00', 'side': 'BUY', 'entry_price': 35.2, 'stop_price': 34.8539, 'take_profit_price': 35.8922, 'exit_ts': '2025-04-08 19:00:00+00:00', 'exit_reason': 'session_end'}
- fills: [{'template_id': 'ib_HOOD_20250408_181500', 'fill_ts': '2025-04-08 18:15:00+00:00', 'fill_price': 35.38}, {'template_id': 'ib_HOOD_20250408_181500', 'fill_ts': '2025-04-08 18:25:00+00:00', 'fill_price': 34.8539}]
- trade: [{'template_id': 'ib_HOOD_20250408_181500', 'entry_price': 35.38, 'exit_price': 34.8539, 'pnl': -146.7818999999999}]

## 260202_090625_HOOD_IB_maxLossPct0_300d
### case 1: template_id=ib_HOOD_20250407_185500 symbol=HOOD signal_ts=2025-04-07 18:55:00+00:00
- suspicious fields: dbg_trigger_ts=2025-04-07 18:55:00+00:00, dbg_exit_ts_ny=2025-04-07 15:00:00-04:00, dbg_valid_to_ts_utc=2025-04-07 19:00:00+00:00, exit_ts=2025-04-07 19:00:00+00:00, exit_reason=session_end
- intent subset: {'template_id': 'ib_HOOD_20250407_185500', 'symbol': 'HOOD', 'signal_ts': '2025-04-07 18:55:00+00:00', 'side': 'SELL', 'entry_price': np.float64(34.56), 'stop_price': np.float64(34.96), 'take_profit_price': np.float64(33.760000000000005), 'exit_ts': '2025-04-07 19:00:00+00:00', 'exit_reason': 'session_end'}
- fills: [{'template_id': 'ib_HOOD_20250407_185500', 'fill_ts': '2025-04-07 18:55:00+00:00', 'fill_price': 34.66}, {'template_id': 'ib_HOOD_20250407_185500', 'fill_ts': '2025-04-07 19:00:00+00:00', 'fill_price': 34.96}]
- trade: [{'template_id': 'ib_HOOD_20250407_185500', 'entry_price': 34.66, 'exit_price': 34.96, 'pnl': -86.40000000000123}]

### case 2: template_id=ib_HOOD_20250407_185500 symbol=HOOD signal_ts=2025-04-07 18:55:00+00:00
- suspicious fields: dbg_trigger_ts=2025-04-07 18:55:00+00:00, dbg_exit_ts_ny=2025-04-07 15:00:00-04:00, dbg_valid_to_ts_utc=2025-04-07 19:00:00+00:00, exit_ts=2025-04-07 19:00:00+00:00, exit_reason=session_end
- intent subset: {'template_id': 'ib_HOOD_20250407_185500', 'symbol': 'HOOD', 'signal_ts': '2025-04-07 18:55:00+00:00', 'side': 'SELL', 'entry_price': np.float64(34.56), 'stop_price': np.float64(34.96), 'take_profit_price': np.float64(33.760000000000005), 'exit_ts': '2025-04-07 19:00:00+00:00', 'exit_reason': 'session_end'}
- fills: [{'template_id': 'ib_HOOD_20250407_185500', 'fill_ts': '2025-04-07 18:55:00+00:00', 'fill_price': 34.66}, {'template_id': 'ib_HOOD_20250407_185500', 'fill_ts': '2025-04-07 19:00:00+00:00', 'fill_price': 34.96}]
- trade: [{'template_id': 'ib_HOOD_20250407_185500', 'entry_price': 34.66, 'exit_price': 34.96, 'pnl': -86.40000000000123}]

### case 3: template_id=ib_HOOD_20250407_185500 symbol=HOOD signal_ts=2025-04-07 18:55:00+00:00
- suspicious fields: dbg_trigger_ts=2025-04-07 18:55:00+00:00, dbg_exit_ts_ny=2025-04-07 15:00:00-04:00, dbg_valid_to_ts_utc=2025-04-07 19:00:00+00:00, exit_ts=2025-04-07 19:00:00+00:00, exit_reason=session_end
- intent subset: {'template_id': 'ib_HOOD_20250407_185500', 'symbol': 'HOOD', 'signal_ts': '2025-04-07 18:55:00+00:00', 'side': 'SELL', 'entry_price': 34.56, 'stop_price': 34.96, 'take_profit_price': 33.760000000000005, 'exit_ts': '2025-04-07 19:00:00+00:00', 'exit_reason': 'session_end'}
- fills: [{'template_id': 'ib_HOOD_20250407_185500', 'fill_ts': '2025-04-07 18:55:00+00:00', 'fill_price': 34.66}, {'template_id': 'ib_HOOD_20250407_185500', 'fill_ts': '2025-04-07 19:00:00+00:00', 'fill_price': 34.96}]
- trade: [{'template_id': 'ib_HOOD_20250407_185500', 'entry_price': 34.66, 'exit_price': 34.96, 'pnl': -86.40000000000123}]

### case 4: template_id=ib_HOOD_20250408_134000 symbol=HOOD signal_ts=2025-04-08 13:40:00+00:00
- suspicious fields: dbg_trigger_ts=2025-04-08 13:40:00+00:00, dbg_exit_ts_ny=2025-04-08 11:00:00-04:00, dbg_valid_to_ts_utc=2025-04-08 15:00:00+00:00, exit_ts=2025-04-08 15:00:00+00:00, exit_reason=session_end
- intent subset: {'template_id': 'ib_HOOD_20250408_134000', 'symbol': 'HOOD', 'signal_ts': '2025-04-08 13:40:00+00:00', 'side': 'SELL', 'entry_price': 36.5, 'stop_price': 36.9, 'take_profit_price': 35.7, 'exit_ts': '2025-04-08 15:00:00+00:00', 'exit_reason': 'session_end'}
- fills: [{'template_id': 'ib_HOOD_20250408_134000', 'fill_ts': '2025-04-08 13:40:00+00:00', 'fill_price': 36.86}, {'template_id': 'ib_HOOD_20250408_134000', 'fill_ts': '2025-04-08 13:45:00+00:00', 'fill_price': 36.9}]
- trade: [{'template_id': 'ib_HOOD_20250408_134000', 'entry_price': 36.86, 'exit_price': 36.9, 'pnl': -10.719999999999771}]

### case 5: template_id=ib_HOOD_20250408_181500 symbol=HOOD signal_ts=2025-04-08 18:15:00+00:00
- suspicious fields: dbg_trigger_ts=2025-04-08 18:15:00+00:00, dbg_exit_ts_ny=2025-04-08 15:00:00-04:00, dbg_valid_to_ts_utc=2025-04-08 19:00:00+00:00, exit_ts=2025-04-08 19:00:00+00:00, exit_reason=session_end
- intent subset: {'template_id': 'ib_HOOD_20250408_181500', 'symbol': 'HOOD', 'signal_ts': '2025-04-08 18:15:00+00:00', 'side': 'BUY', 'entry_price': 35.2, 'stop_price': 34.8539, 'take_profit_price': 35.8922, 'exit_ts': '2025-04-08 19:00:00+00:00', 'exit_reason': 'session_end'}
- fills: [{'template_id': 'ib_HOOD_20250408_181500', 'fill_ts': '2025-04-08 18:15:00+00:00', 'fill_price': 35.38}, {'template_id': 'ib_HOOD_20250408_181500', 'fill_ts': '2025-04-08 18:25:00+00:00', 'fill_price': 34.8539}]
- trade: [{'template_id': 'ib_HOOD_20250408_181500', 'entry_price': 35.38, 'exit_price': 34.8539, 'pnl': -146.7818999999999}]

## 260203_221225_HOOD_IB_allign2golden_300d
### case 1: template_id=ib_HOOD_20250408_142500 symbol=HOOD signal_ts=2025-04-08 14:25:00+00:00
- suspicious fields: dbg_trigger_ts=2025-04-08 14:25:00+00:00, dbg_exit_ts_ny=2025-04-08 11:00:00-04:00, dbg_valid_to_ts_utc=2025-04-08 15:00:00+00:00, exit_ts=2025-04-08 15:00:00+00:00, exit_reason=session_end
- intent subset: {'template_id': 'ib_HOOD_20250408_142500', 'symbol': 'HOOD', 'signal_ts': '2025-04-08 14:25:00+00:00', 'side': 'SELL', 'entry_price': np.float64(37.36), 'stop_price': np.float64(37.76), 'take_profit_price': np.float64(36.56), 'exit_ts': '2025-04-08 15:00:00+00:00', 'exit_reason': 'session_end'}
- fills: [{'template_id': 'ib_HOOD_20250408_142500', 'fill_ts': '2025-04-08 14:25:00+00:00', 'fill_price': 37.356264}, {'template_id': 'ib_HOOD_20250408_142500', 'fill_ts': '2025-04-08 14:55:00+00:00', 'fill_price': 36.56}]
- trade: [{'template_id': 'ib_HOOD_20250408_142500', 'entry_price': 37.356264, 'exit_price': 36.56, 'pnl': 212.6024879999983}]

### case 2: template_id=ib_HOOD_20250408_142500 symbol=HOOD signal_ts=2025-04-08 14:25:00+00:00
- suspicious fields: dbg_trigger_ts=2025-04-08 14:25:00+00:00, dbg_exit_ts_ny=2025-04-08 11:00:00-04:00, dbg_valid_to_ts_utc=2025-04-08 15:00:00+00:00, exit_ts=2025-04-08 15:00:00+00:00, exit_reason=session_end
- intent subset: {'template_id': 'ib_HOOD_20250408_142500', 'symbol': 'HOOD', 'signal_ts': '2025-04-08 14:25:00+00:00', 'side': 'SELL', 'entry_price': np.float64(37.36), 'stop_price': np.float64(37.76), 'take_profit_price': np.float64(36.56), 'exit_ts': '2025-04-08 15:00:00+00:00', 'exit_reason': 'session_end'}
- fills: [{'template_id': 'ib_HOOD_20250408_142500', 'fill_ts': '2025-04-08 14:25:00+00:00', 'fill_price': 37.356264}, {'template_id': 'ib_HOOD_20250408_142500', 'fill_ts': '2025-04-08 14:55:00+00:00', 'fill_price': 36.56}]
- trade: [{'template_id': 'ib_HOOD_20250408_142500', 'entry_price': 37.356264, 'exit_price': 36.56, 'pnl': 212.6024879999983}]

### case 3: template_id=ib_HOOD_20250408_142500 symbol=HOOD signal_ts=2025-04-08 14:25:00+00:00
- suspicious fields: dbg_trigger_ts=2025-04-08 14:25:00+00:00, dbg_exit_ts_ny=2025-04-08 11:00:00-04:00, dbg_valid_to_ts_utc=2025-04-08 15:00:00+00:00, exit_ts=2025-04-08 15:00:00+00:00, exit_reason=session_end
- intent subset: {'template_id': 'ib_HOOD_20250408_142500', 'symbol': 'HOOD', 'signal_ts': '2025-04-08 14:25:00+00:00', 'side': 'SELL', 'entry_price': 37.36, 'stop_price': 37.76, 'take_profit_price': 36.56, 'exit_ts': '2025-04-08 15:00:00+00:00', 'exit_reason': 'session_end'}
- fills: [{'template_id': 'ib_HOOD_20250408_142500', 'fill_ts': '2025-04-08 14:25:00+00:00', 'fill_price': 37.356264}, {'template_id': 'ib_HOOD_20250408_142500', 'fill_ts': '2025-04-08 14:55:00+00:00', 'fill_price': 36.56}]
- trade: [{'template_id': 'ib_HOOD_20250408_142500', 'entry_price': 37.356264, 'exit_price': 36.56, 'pnl': 212.6024879999983}]

### case 4: template_id=ib_HOOD_20250408_181500 symbol=HOOD signal_ts=2025-04-08 18:15:00+00:00
- suspicious fields: dbg_trigger_ts=2025-04-08 18:15:00+00:00, dbg_exit_ts_ny=2025-04-08 15:00:00-04:00, dbg_valid_to_ts_utc=2025-04-08 19:00:00+00:00, exit_ts=2025-04-08 19:00:00+00:00, exit_reason=session_end
- intent subset: {'template_id': 'ib_HOOD_20250408_181500', 'symbol': 'HOOD', 'signal_ts': '2025-04-08 18:15:00+00:00', 'side': 'BUY', 'entry_price': 35.2, 'stop_price': 34.8539, 'take_profit_price': 35.8922, 'exit_ts': '2025-04-08 19:00:00+00:00', 'exit_reason': 'session_end'}
- fills: [{'template_id': 'ib_HOOD_20250408_181500', 'fill_ts': '2025-04-08 18:15:00+00:00', 'fill_price': 35.203520000000005}, {'template_id': 'ib_HOOD_20250408_181500', 'fill_ts': '2025-04-08 18:25:00+00:00', 'fill_price': 34.8539}]
- trade: [{'template_id': 'ib_HOOD_20250408_181500', 'entry_price': 35.203520000000005, 'exit_price': 34.8539, 'pnl': -101.38980000000046}]

### case 5: template_id=ib_HOOD_20250409_134000 symbol=HOOD signal_ts=2025-04-09 13:40:00+00:00
- suspicious fields: dbg_trigger_ts=2025-04-09 13:40:00+00:00, dbg_exit_ts_ny=2025-04-09 11:00:00-04:00, dbg_valid_to_ts_utc=2025-04-09 15:00:00+00:00, exit_ts=2025-04-09 15:00:00+00:00, exit_reason=session_end
- intent subset: {'template_id': 'ib_HOOD_20250409_134000', 'symbol': 'HOOD', 'signal_ts': '2025-04-09 13:40:00+00:00', 'side': 'BUY', 'entry_price': 34.86, 'stop_price': 34.46, 'take_profit_price': 35.66, 'exit_ts': '2025-04-09 15:00:00+00:00', 'exit_reason': 'session_end'}
- fills: [{'template_id': 'ib_HOOD_20250409_134000', 'fill_ts': '2025-04-09 13:40:00+00:00', 'fill_price': 34.863486}, {'template_id': 'ib_HOOD_20250409_134000', 'fill_ts': '2025-04-09 13:45:00+00:00', 'fill_price': 34.46}]
- trade: [{'template_id': 'ib_HOOD_20250409_134000', 'entry_price': 34.863486, 'exit_price': 34.46, 'pnl': -117.01094000000026}]

