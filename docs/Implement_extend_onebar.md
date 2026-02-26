# Exit-Strategie Erweiterung - Implementierungsplan

**Datum**: 2026-01-02  
**Basis**: Analyse_extend_onebar.md  
**Ziel**: Schrittweiser Plan für Parametrisierung & Erweiterung der Exit-Strategien

---

## Zusammenfassung der Erkenntnisse

**Ausgangslage** (aus Analyse):
- 3 von 4 User-Optionen sind bereits **implementiert** (fixed_bars, session_end, fixed_minutes)
- Namen zwischen User-Request und Code **divergieren** (z.B. "minute-based" vs "fixed_minutes")
- **Kritisches Architektur-Problem**: SessionFilter-Coupling (Framework ← Strategy)
- **EOD** ist unklar definiert (erfordert User-Klärung)

**Empfohlene Vorgehensweise**:
1. **Phase 0**: User-Klärung (Blocker-Fragen)
2. **Phase 1**: Architektur-Refactoring (SessionFilter entkoppeln) - OPTIONAL aber empfohlen
3. **Phase 2**: EOD-Policy implementieren (nach Klärung)
4. **Phase 3**: Naming harmonisieren + Dokumentation
5. **Phase 4**: Verification Tests

---

## Phase 0: User-Klärungssession (KRITISCH - vor Implementierung)

### Blocker-Fragen (MUST-ANSWER)

**Frage 1: EOD-Definition**
```
Was bedeutet "EOD" (End Of Day) konkret?

Option A: End of Trading Day (Market Close)
  - US equities: 16:00 ET (= RTH Ende)
  - EUR equities: 17:30 CET (= XETRA Close)
  
Option B: End of last Session Window
  - InsideBar: 17:00 Berlin (Session 2 Ende)
  - Strategie-spezifisch
  
Option C: End of available backtest data
  - Letzte Bar im Backtest-Dataset

Welche Option ist korrekt?
```

**Frage 2: "minute-based" Semantik**
```
Ist "minute-based" identisch mit der bereits implementierten "fixed_minutes" Policy?

fixed_minutes Verhalten:
- Order gültig für N Minuten (z.B. 30)
- Wird geclampt auf session_end wenn über Session-Grenze hinaus

Falls NICHT identisch: Was ist der Unterschied?
```

**Frage 3: EOD Timezone** (falls EOD = Market Close)
```
In welcher Timezone soll EOD berechnet werden?

Option A: Market-spezifisch hard-coded
  - US markets → America/New_York
  - EUR markets → Europe/Berlin
  
Option B: Strategy-konfigurierbar
  - Parameter "eod_timezone" in Strategy Config

Welche Option bevorzugt?
```

**Frage 4: Multiple Positions**
```
Mit EOD Policy könnten mehrere gleichzeitige Positionen entstehen, z.B.:
- Signal Session 1 at 15:30 → Entry 15:35, EOD valid_until = 17:00
- Signal Session 2 at 16:05 → Entry 16:06, EOD valid_until = 17:00
→ Beide Positionen von 16:06 bis 17:00 gleichzeitig offen

Ist das gewollt/erlaubt?
```

---

## Phase 1: Architektur-Refactoring (SessionFilter entkoppeln)

### Goal: Framework-unabhängig von spezifischen Strategien

**Warum JETZT?**:
- EOD-Implementierung würde **gleiches Coupling-Problem** erzeugen
- Besser: Einmal sauber refactoren, dann EOD auf sauberer Basis implementieren

**Empfehlung**: Machen. Falls zeitkritisch → überspringen und später nachziehen, ABER dann bleibt Coupling.

---

### Schritt 1.1: SessionInterface Protocol erstellen

**File**: `src/axiom_bt/contracts/session_interface.py` (NEU)

**Inhalt**:
```python
"""
Session boundary interface for validity calculations.

Provides abstraction for determining session boundaries,
allowing strategies to implement their own session logic
without coupling the framework to specific implementations.
"""
from abc import ABC, abstractmethod
from typing import Optional
import pandas as pd


class SessionInterface(ABC):
    """
    Interface for session boundary calculations.
    
    Strategies implement this protocol to provide session-end
    timestamps for validity window calculations.
    """
    
    @abstractmethod
    def get_session_end(
        self,
        timestamp: pd.Timestamp,
        timezone: str
    ) -> Optional[pd.Timestamp]:
        """
        Get session end timestamp for given timestamp.
        
        Args:
            timestamp: TZ-aware timestamp to check
            timezone: Session timezone (e.g., "Europe/Berlin")
        
        Returns:
            Session end timestamp (TZ-aware) or None if not in session
        
        Raises:
            ValueError: If timestamp is naive (no timezone)
        """
        pass
    
    @abstractmethod
    def is_in_session(
        self,
        timestamp: pd.Timestamp,
        timezone: str
    ) -> bool:
        """
        Check if timestamp is within any session window.
        """
        pass
```

**Rationale**: Klares Interface ohne Implementierungs-Details.

---

### Schritt 1.2: InsideBar SessionFilter an Interface anpassen

**File**: `src/strategies/inside_bar/config.py`

**Änderung**: Klasse erbt von `SessionInterface`:

```python
from axiom_bt.contracts.session_interface import SessionInterface

class SessionFilter(SessionInterface):  # ← erbevon Interface
    """
    InsideBar-specific session filter implementation.
    """
    
    # Existing methods...
    def get_session_end(self, timestamp, timezone):
        # Existing implementation bleibt
        ...
    
    def is_in_session(self, timestamp, timezone):
        # Existing implementation bleibt
        ...
```

**Effort**: MINIMAL (nur Vererbung hinzufügen)

---

### Schritt 1.3: validity.py auf Interface umstellen

**File**: `src/trade/validity.py`

**Änderung Line 15**:

```python
# VORHER:
from strategies.inside_bar.config import SessionFilter  # ← Coupling!

# NACHHER:
from axiom_bt.contracts.session_interface import SessionInterface
```

**Änderung Line 21, 49**:

```python
# VORHER:
def calculate_validity_window(
    ...
    session_filter: SessionFilter,  # ← Konkrete Klasse
    ...
):

# NACHHER:
def calculate_validity_window(
    ...
    session_filter: SessionInterface,  # ← Interface
    ...
):
```

**Effort**: MINIMAL (2 Zeilen Änderung)

---

### Schritt 1.4: Verification Tests für Refactoring

**Test 1**: SessionInterface Contract Test

**File**: `tests/test_session_interface.py` (NEU)

```python
"""
Test SessionInterface protocol compliance.
"""
import pytest
import pandas as pd
from axiom_bt.contracts.session_interface import SessionInterface
from strategies.inside_bar.config import SessionFilter

def test_insidebar_sessionfilter_implements_interface():
    """Verify InsideBar SessionFilter implements SessionInterface."""
    assert issubclass(SessionFilter, SessionInterface)
    
def test_session_interface_abstract():
    """Verify SessionInterface cannot be instantiated."""
    with pytest.raises(TypeError):
        SessionInterface()

def test_sessionfilter_get_session_end():
    """Test SessionFilter.get_session_end returns TZ-aware timestamp."""
    sf = SessionFilter.from_strings(["15:00-16:00"])
    ts = pd.Timestamp("2025-11-28 15:30:00", tz="Europe/Berlin")
    session_end = sf.get_session_end(ts, "Europe/Berlin")
    
    assert session_end is not None
    assert session_end.tz is not None  # TZ-aware
    assert session_end == pd.Timestamp("2025-11-28 16:00:00", tz="Europe/Berlin")
```

**Run**: `PYTHONPATH=src python -m pytest tests/test_session_interface.py -v`

**Test 2**: validity.py nicht mehr abhängig von InsideBar

**File**: `tests/test_validity_independence.py` (NEU)

```python
"""
Verify validity.py can work without InsideBar imports.
"""
import sys
import pytest

def test_validity_no_insidebar_import():
    """
    Verify trade.validity does not import InsideBar strategy modules.
    """
    # Remove InsideBar from sys.modules if present
    modules_to_remove = [k for k in sys.modules if 'inside_bar' in k]
    for mod in modules_to_remove:
        del sys.modules[mod]
    
    # Now import validity - should NOT fail
    from trade import validity
    
    # Verify calculate_validity_window exists
    assert hasattr(validity, 'calculate_validity_window')
```

**Run**: `PYTHONPATH=src python -m pytest tests/test_validity_independence.py -v`

---

### Phase 1 Summary

**Files geändert**: 3
- `src/axiom_bt/contracts/session_interface.py` (NEU, ~50 lines)
- `src/strategies/inside_bar/config.py` (1 line: Vererbung)
- `src/trade/validity.py` (2 lines: Import + Type Annotation)

**Files erstellt (Tests)**: 2
- `tests/test_session_interface.py` (~30 lines)
- `tests/test_validity_independence.py` (~20 lines)

**Breaking Changes**: KEINE (nur Interface eingeführt, keine Funktionalität geändert)

**Effort**: 🟢 **LOW** (1-2 Stunden)

**Benefit**: 🔴 **HIGH** (saubere Architektur, wiederverwendbar für DAX/andere Strategien)

---

## Phase 2: EOD Policy Implementierung

### Voraussetzung: Phase 0 Blocker-Fragen beantwortet

**Annahme für Beispiel** (muss mit User bestätigt werden):
- EOD = End of Trading Day (Market Close)
- US markets: 16:00 ET
- EUR markets: 17:30 CET
- Konfigurierbar per Strategy-Parameter

---

### Schritt 2.1: EODTimestampProvider erstellen

**File**: `src/axiom_bt/contracts/eod_provider.py` (NEU)

**Inhalt**:
```python
"""
End of Day (EOD) timestamp provider interface.
"""
from abc import ABC, abstractmethod
import pandas as pd


class EODProvider(ABC):
    """
    Interface for determining End of Trading Day timestamps.
    """
    
    @abstractmethod
    def get_eod(
        self,
        timestamp: pd.Timestamp,
        timezone: str
    ) -> pd.Timestamp:
        """
        Get End of Day timestamp for given trading day.
        
        Args:
            timestamp: TZ-aware timestamp within trading day
            timezone: Trading timezone
        
        Returns:
            EOD timestamp (TZ-aware)
        
        Example:
            >>> # US market
            >>> eod = provider.get_eod(
            ...     pd.Timestamp("2025-11-28 10:00", tz="America/New_York"),
            ...     "America/New_York"
            ... )
            >>> assert eod == pd.Timestamp("2025-11-28 16:00", tz="America/New_York")
        """
        pass


class MarketCloseEODProvider(EODProvider):
    """
    EOD provider using market close times.
    """
    
    def __init__(self, close_time: str):
        """
        Args:
            close_time: Market close time as "HH:MM" (e.g., "16:00")
        """
        self.close_time = close_time
        hour, minute = close_time.split(":")
        self.close_hour = int(hour)
        self.close_minute = int(minute)
    
    def get_eod(self, timestamp: pd.Timestamp, timezone: str) -> pd.Timestamp:
        """Get EOD as market close time on same trading day."""
        if timestamp.tz is None:
            raise ValueError("timestamp must be timezone-aware")
        
        # Convert to target timezone
        ts_local = timestamp.tz_convert(timezone)
        
        # Create EOD at close time on same day
        eod = ts_local.replace(
            hour=self.close_hour,
            minute=self.close_minute,
            second=0,
            microsecond=0
        )
        
        # If timestamp is already after close, use next trading day
        # (simplified - ignores weekends/holidays)
        if ts_local.time() > eod.time():
            eod = eod + pd.Timedelta(days=1)
        
        return eod
```

**Rationale**: Wiederverwendbar, testbar, strategy-unabhängig.

---

### Schritt 2.2: validity.py um EOD Policy erweitern

**File**: `src/trade/validity.py`

**Änderung Line 18** (Signature):

```python
# Neuer Parameter hinzufügen:
def calculate_validity_window(
    signal_ts: pd.Timestamp,
    timeframe_minutes: int,
    session_filter: SessionInterface,
    session_timezone: str,
    validity_policy: str,
    validity_minutes: int = 60,
    valid_from_policy: str = "signal_ts",
    eod_provider: Optional[EODProvider] = None,  # ← NEU
) -> Tuple[pd.Timestamp, pd.Timestamp]:
```

**Änderung nach Line 142** (neuer elif-Block):

```python
elif validity_policy == "eod":
    # Order valid until End of Trading Day
    if eod_provider is None:
        raise ValueError(
            "validity_policy='eod' requires eod_provider argument. "
            "Pass an EODProvider instance (e.g., MarketCloseEODProvider)."
        )
    
    try:
        valid_to = eod_provider.get_eod(valid_from, session_timezone)
    except Exception as e:
        raise ValueError(
            f"EOD provider error for valid_from ({valid_from}): {e}"
        )
    
    # Safety check: EOD must be after valid_from
    if valid_to <= valid_from:
        raise ValueError(
            f"EOD ({valid_to}) is at or before valid_from ({valid_from}). "
            "This can happen if signal is after market close. Order rejected."
        )

else:
    raise ValueError(
        f"Unknown validity_policy: {validity_policy}. "
        "Must be 'session_end', 'fixed_minutes', 'fixed_bars', or 'eod'."  # ← aktualisiert
    )
```

**Änderung Line 147** (Error Message):

```python
# VORHER:
"Must be 'session_end', 'fixed_minutes', or 'fixed_bars'."

# NACHHER:
"Must be 'session_end', 'fixed_minutes', 'fixed_bars', or 'eod'."
```

**Effort**: 🟢 **LOW** (~30 Zeilen Code)

---

### Schritt 2.3: InsideBar Config um EOD erweitern

**File**: `src/strategies/inside_bar/config.py`

**Änderung** (neue Fields in InsideBarConfig):

```python
class InsideBarConfig(BaseModel):
    # ... existing fields ...
    
    order_validity_policy: str = "session_end"
    order_validity_minutes: int = 60  # For fixed_minutes
    
    # NEU:
    eod_close_time: str = "17:00"  # Market close for EOD policy (HH:MM format)
    
    def __post_init__(self):
        # Existing validations...
        
        # Update valid policies
        assert self.order_validity_policy in [
            "session_end", "fixed_minutes", "fixed_bars", "eod"  # ← eod hinzugefügt
        ], (
            f"Invalid order_validity_policy: {self.order_validity_policy} "
            "('instant' removed - use 'fixed_bars' for single-bar validity)"
        )
```

**Effort**: 🟢 **MINIMAL** (2 lines)

---

### Schritt 2.4: OrdersBuilder um EOD Support erweitern

**File**: `src/trade/orders_builder.py`

**Änderung** (calculate_validity_window Call anpassen):

```python
# Irgendwo um Line 180-200 (finde genaue Stelle im Code):

# Prepare EOD provider if needed
eod_provider = None
if validity_policy == "eod":
    from axiom_bt.contracts.eod_provider import MarketCloseEODProvider
    eod_close_time = strategy_params.get("eod_close_time", "16:00")
    eod_provider = MarketCloseEODProvider(eod_close_time)

# Call validity calculation
valid_from, valid_to = calculate_validity_window(
    signal_ts=sig.signal_ts,
    timeframe_minutes=timeframe_minutes,
    session_filter=session_filter,
    session_timezone=session_timezone,
    validity_policy=validity_policy,
    validity_minutes=validity_minutes,
    valid_from_policy=valid_from_policy,
    eod_provider=eod_provider,  # ← NEU
)
```

**Effort**: 🟡 **MEDIUM** (genaue Code-Stelle finden + 10 Zeilen Code)

---

### Schritt 2.5: Dokumentation aktualisieren

**File**: `src/strategies/inside_bar/docs/INSIDE_BAR_SSOT.md`

**Änderung Line 18** (Options Liste):

```markdown
# VORHER:
- **Options**: `session_end`, `fixed_bars`, `fixed_minutes`

# NACHHER:
- **Options**: `session_end`, `fixed_bars`, `fixed_minutes`, `eod`
```

**Änderung nach Line 20** (neue Beschreibung):

```markdown
#### EOD (End of Trading Day) Policy

- **Semantics**: Order valid until market close (e.g., 16:00 ET for US, 17:30 CET for EUR)
- **Configuration**: `eod_close_time` parameter (format "HH:MM")
- **Use case**: Longer validity window, allows positions across multiple sessions
- **Constraint**: Multiple simultaneous positions possible (if signals in different sessions)
```

**Effort**: 🟢 **MINIMAL** (5 lines)

---

### Phase 2 Summary

**Files geändert/erstellt**: 5
- `src/axiom_bt/contracts/eod_provider.py` (NEU, ~80 lines)
- `src/trade/validity.py` (+20 lines)
- `src/strategies/inside_bar/config.py` (+3 lines)
- `src/trade/orders_builder.py` (+10 lines)
- `src/strategies/inside_bar/docs/INSIDE_BAR_SSOT.md` (+5 lines)

**Effort**: 🟡 **MEDIUM** (2-3 Stunden)

**Breaking Changes**: KEINE (neue Policy ist opt-in)

---

## Phase 3: Naming Harmonisierung

### Ziel: User-Namen = Code-Namen

**Aktuelle Diskrepanz**:

| User-Name | Code-Name | Action |
|-----------|-----------|--------|
| fixed_bars | fixed_bars | ✅ OK |
| **minute-based** | **fixed_minutes** | ⚠️ Umbenennen? |
| **end of session window** | **session_end** | ⚠️ Umbenennen? |
| EOD | eod | ✅ OK |

**Recommendation**: **NICHT umbenennen**, stattdessen **Dokumentation angleichen**.

**Warum?**:
- Code-Namen sind etabliert
- Umbenennung = Breaking Change für existierende Configs
- Besser: User-Doku nutzt Code-Namen

---

### Schritt 3.1: Dokumentation mit Code-Namen harmonisieren

**File**: `docs/INSIDE_BAR_SSOT.md`, `README.md`, etc.

**Änderungen**:
- Überall wo "minute-based" steht → ersetzen mit "`fixed_minutes`"
- Überall wo "end of session window" steht → ersetzen mit "`session_end`"
- Klare Definition hinzufügen: "Policy names use snake_case (e.g., `fixed_minutes`, not 'minute-based')"

**Effort**: 🟢 **LOW** (Search & Replace)

---

### Schritt 3.2: UI Labels (falls Streamlit Dashboard vorhanden)

**Falls** ein Streamlit-Dashboard existiert mit Policy-Auswahl:

**File**: `apps/streamlit/...` (finde relevantes UI-Modul)

**Änderung**: Dropdown-Labels = Code-Namen

```python
# VORHER (hypothetisch):
policy = st.selectbox(
    "Order Validity Policy",
    options=["One Bar", "Minute-Based", "End of Session"]
)

# NACHHER:
policy = st.selectbox(
    "Order Validity Policy",
    options=["fixed_bars", "fixed_minutes", "session_end", "eod"],
    help="How long orders remain valid after signal"
)
```

**Effort**: 🟡 **MEDIUM** (abhängig von UI-Komplexität)

---

## Phase 4: Verification & Testing

### Test-Suite für EOD Policy

#### Test 1: EOD Provider Unit Tests

**File**: `tests/test_eod_provider.py` (NEU)

```python
"""
Test EODProvider implementations.
"""
import pytest
import pandas as pd
from axiom_bt.contracts.eod_provider import MarketCloseEODProvider


def test_market_close_eod_us_market():
    """Test EOD for US market (16:00 ET close)."""
    provider = MarketCloseEODProvider("16:00")
    
    # Signal at 10:00 ET
    ts = pd.Timestamp("2025-11-28 10:00:00", tz="America/New_York")
    eod = provider.get_eod(ts, "America/New_York")
    
    # EOD should be 16:00 same day
    expected = pd.Timestamp("2025-11-28 16:00:00", tz="America/New_York")
    assert eod == expected


def test_market_close_eod_after_close():
    """Test EOD when signal is after market close."""
    provider = MarketCloseEODProvider("16:00")
    
    # Signal at 18:00 (after close)
    ts = pd.Timestamp("2025-11-28 18:00:00", tz="America/New_York")
    eod = provider.get_eod(ts, "America/New_York")
    
    # EOD should be next day 16:00
    expected = pd.Timestamp("2025-11-29 16:00:00", tz="America/New_York")
    assert eod == expected


def test_eod_provider_naive_timestamp_error():
    """Test EOD provider rejects naive timestamps."""
    provider = MarketCloseEODProvider("16:00")
    ts_naive = pd.Timestamp("2025-11-28 10:00:00")  # No timezone
    
    with pytest.raises(ValueError, match="timezone-aware"):
        provider.get_eod(ts_naive, "America/New_York")
```

**Run**: `PYTHONPATH=src python -m pytest tests/test_eod_provider.py -v`

---

#### Test 2: validity.py EOD Policy Integration Test

**File**: `tests/test_validity_eod.py` (NEU)

```python
"""
Test validity.py with EOD policy.
"""
import pytest
import pandas as pd
from trade.validity import calculate_validity_window
from axiom_bt.contracts.eod_provider import MarketCloseEODProvider
from strategies.inside_bar.config import SessionFilter


def test_eod_policy_basic():
    """Test EOD policy calculates validity to market close."""
    signal_ts = pd.Timestamp("2025-11-28 15:30:00", tz="America/New_York")
    session_filter = SessionFilter.from_strings(["15:00-16:00"])
    eod_provider = MarketCloseEODProvider("16:00")
    
    valid_from, valid_to = calculate_validity_window(
        signal_ts=signal_ts,
        timeframe_minutes=5,
        session_filter=session_filter,
        session_timezone="America/New_York",
        validity_policy="eod",
        eod_provider=eod_provider
    )
    
    assert valid_from == signal_ts
    assert valid_to == pd.Timestamp("2025-11-28 16:00:00", tz="America/New_York")
    assert (valid_to - valid_from).total_seconds() == 1800  # 30 minutes


def test_eod_policy_without_provider_error():
    """Test EOD policy requires eod_provider."""
    signal_ts = pd.Timestamp("2025-11-28 15:30:00", tz="America/New_York")
    session_filter = SessionFilter.from_strings(["15:00-16:00"])
    
    with pytest.raises(ValueError, match="requires eod_provider"):
        calculate_validity_window(
            signal_ts=signal_ts,
            timeframe_minutes=5,
            session_filter=session_filter,
            session_timezone="America/New_York",
            validity_policy="eod",
            eod_provider=None  # ← Missing!
        )
```

**Run**: `PYTHONPATH=src python -m pytest tests/test_validity_eod.py -v`

---

#### Test 3: End-to-End Backtest mit EOD Policy

**File**: `tests/test_backtest_eod_policy_e2e.py` (NEU)

**Ziel**: Kompletter Backtest-Run mit EOD Policy, prüfen ob Fills korrekt erfolgen.

```python
"""
End-to-end test for EOD policy in backtest.
"""
import pytest
from pathlib import Path
import pandas as pd


@pytest.mark.integration
def test_backtest_with_eod_policy(tmp_path):
    """
    Run full backtest with EOD policy and verify fills occur.
    """
    # Setup test config
    strategy_params = {
        "symbol": "TSLA",
        "session_windows": ["15:00-16:00", "16:00-17:00"],
        "session_timezone": "Europe/Berlin",
        "order_validity_policy": "eod",  # ← Test EOD
        "eod_close_time": "17:00",
        # ... other params
    }
    
    # Run backtest
        strategy_name="inside_bar",
        strategy_key="insidebar_intraday",
        symbol="TSLA",
        strategy_params=strategy_params,
        requested_end="2025-11-28",
        lookback_days=10,
        artifacts_root=tmp_path
    )
    
    # Verify orders were created with EOD validity
    orders_csv = tmp_path / result["run_id"] / "orders.csv"
    assert orders_csv.exists()
    
    orders = pd.read_csv(orders_csv, parse_dates=["valid_from", "valid_to"])
    
    # Check validity windows extend to 17:00 (eod_close_time)
    for _, order in orders.iterrows():
        valid_to_time = order["valid_to"].time()
        assert valid_to_time == pd.Timestamp("17:00").time(), (
            f"Expected valid_to at 17:00, got {valid_to_time}"
        )
    
    # Verify fills occurred (if data supports it)
    filled_orders = result.get("filled_orders")
    if filled_orders is not None and not filled_orders.empty:
        # EOD policy should enable fills
        assert len(filled_orders) > 0, "EOD policy should allow fills"
```

**Run**: `PYTHONPATH=src python -m pytest tests/test_backtest_eod_policy_e2e.py -v -m integration`

**Prerequisite**: Test data für TSLA 10 Tage verfügbar.

---

### Test Coverage Matrix

| Component | Test File | Test Type | Lines | Run Command |
|-----------|-----------|-----------|-------|-------------|
| **SessionInterface** | test_session_interface.py | Unit | ~30 | `pytest tests/test_session_interface.py` |
| **Validity Independence** | test_validity_independence.py | Integration | ~20 | `pytest tests/test_validity_independence.py` |
| **EOD Provider** | test_eod_provider.py | Unit | ~40 | `pytest tests/test_eod_provider.py` |
| **Validity EOD** | test_validity_eod.py | Integration | ~40 | `pytest tests/test_validity_eod.py` |
| **E2E Backtest EOD** | test_backtest_eod_policy_e2e.py | E2E | ~50 | `pytest -m integration tests/test_backtest_eod_policy_e2e.py` |

**Total Test LOC**: ~180 lines

---

## Zusammenfassung

### Implementierungs-Reihenfolge

| Phase | Name | Effort | Breaking | Tests | Dependencies |
|-------|------|--------|----------|-------|--------------|
| **0** | User-Klärung | - | - | - | NONE |
| **1** | SessionFilter Refactoring | 🟢 LOW | ❌ No | 2 files | Phase 0 |
| **2** | EOD Policy | 🟡 MEDIUM | ❌ No | 3 files | Phase 0, 1 |
| **3** | Naming Harmonisierung | 🟢 LOW | ❌ No | - | Phase 2 |
| **4** | Verification Tests | 🟡 MEDIUM | ❌ No | 5 files | Phase 2 |

**Total Effort**: 🟡 **6-8 Stunden** (assuming User-Klärung erfolgt ist)

---

### Files Created/Modified Summary

**NEU (11 files)**:
- `src/axiom_bt/contracts/session_interface.py`
- `src/axiom_bt/contracts/eod_provider.py`
- `tests/test_session_interface.py`
- `tests/test_validity_independence.py`
- `tests/test_eod_provider.py`
- `tests/test_validity_eod.py`
- `tests/test_backtest_eod_policy_e2e.py`

**MODIFIED (5 files)**:
- `src/strategies/inside_bar/config.py` (~5 lines)
- `src/trade/validity.py` (~25 lines)
- `src/trade/orders_builder.py` (~10 lines)
- `src/strategies/inside_bar/docs/INSIDE_BAR_SSOT.md` (~10 lines)
- `docs/README.md` or relevant user docs (~20 lines)

**Total LOC**: ~400 lines code + tests

---

### Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **User EOD Definition unklar** | 🔴 HIGH | 🔴 HIGH | Phase 0 Klärung MANDATORY |
| **EOD führt zu multiplen Positionen** | 🟡 MEDIUM | 🟡 MEDIUM | Dokumentieren + optional enforceConstraint in Strategy |
| **SessionFilter Refactor bricht Tests** | 🟢 LOW | 🟡 MEDIUM | Umfassende Test-Suite (Phase 1.4) |
| **EOD Provider Timezone-Bugs** | 🟡 MEDIUM | 🔴 HIGH | Unit Tests + TZ-aware validation |
| **Naming Confusion bleibt** | 🟡 MEDIUM | 🟢 LOW | Phase 3 Doku-Harmonisierung |

---

### Definition of Done

**Phase 1 (Refactoring)**:
- [ ] SessionInterface Protocol existiert
- [ ] InsideBar SessionFilter erbt von Interface
- [ ] validity.py importiert nur Interface (nicht konkrete Klasse)
- [ ] Tests: test_session_interface.py alle grün
- [ ] Tests: test_validity_independence.py grün
- [ ] Keine Breaking Changes (existing backtests laufen unverändert)

**Phase 2 (EOD Policy)**:
- [ ] EODProvider Interface + MarketCloseEODProvider implementiert
- [ ] validity.py unterstützt "eod" policy
- [ ] InsideBarConfig akzepiert "eod" + "eod_close_time" parameter
- [ ] OrdersBuilder nutzt EOD Provider wenn policy="eod"
- [ ] Dokumentation beschreibt EOD Policy + Constraints
- [ ] Tests: test_eod_provider.py alle grün
- [ ] Tests: test_validity_eod.py alle grün
- [ ] Tests: E2E test mit EOD Policy grün

**Phase 3 (Naming)**:
- [ ] Alle Doku nutzt Code-Namen (fixed_minutes, session_end, eod)
- [ ] UI (falls vorhanden) nutzt Code-Namen
- [ ] Keine "minute-based" oder "end of session window" Begriffe mehr in User-facing Docs

**Phase 4 (Verification)**:
- [ ] Alle 5 Test-Files erstellt und grün
- [ ] Test Coverage für EOD Path > 80%
- [ ] E2E Test zeigt erfolgreiche Fills mit EOD Policy
- [ ] Keine Regressionen in existing tests

---

## Offene Architektur-Fragen

### Soll Position-Limit enforced werden?

**Aktuell**: InsideBar limitiert Signale (max 1/session), Engine hat kein Limit.

**Mit EOD**: Mehrere Positionen **möglich** (wenn Signale aus verschiedenen Sessions).

**Optionen**:
1. **Status Quo**: Position-Limit nur auf Strategy-Level (Signal-Generation)
   - Pro: Flexibel, andere Strategien können mehrere Positionen wollen
   - Con: Risk wenn Strategy falsch konfiguriert

2. **Engine-Level Position Limit**: `replay_engine` prüft offene Positionen
   - Pro: Safety-Net
   - Con: Komplexer State-Tracking

**Recommendation**: **Status Quo** (Strategy-Level Limit reicht). Falls später nötig → Engine-Level hinzufügen.

---

### Soll GTC (Good Till Cancelled) Policy hinzugefügt werden?

**Hinweis**: `cli_export_orders.py` erwähnt bereits "good_till_cancel".

**Was wäre GTC**:
- Order ohne Expiry (gültig bis SL/TP hit)
- `valid_to` = "unendlich" oder end of backtest data

**Use Case**: Swing-Trading Strategien (multi-day holds).

**Recommendation**: **Nicht jetzt**. Falls Bedarf entsteht → später hinzufügen (gleicher Pattern wie EOD).

---

**Dokument Ende**
