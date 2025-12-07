# Redis Integration Guide

**Status**: Planning/Reference  
**Last Updated**: 2025-12-07  
**Purpose**: Evaluation guide for adding Redis to the trading system

---

## What is Redis?

**Redis** (Remote Dictionary Server) is an in-memory data structure store that can be used as:
- Database
- Cache
- Message broker
- Session store

Think of it as a super-fast key-value store that lives in RAM, making it extremely fast (sub-millisecond response times).

---

## Why Redis Would Benefit Your Trading System

### 1. Job Queue Management (Highest Impact)

**Current Problem**: Dashboard uses Python threading for background backtests
- Jobs lost on restart
- No job persistence
- Limited to single machine
- Hard to scale

**With Redis + Celery**:
```python
# Instead of threading
from celery import Celery
app = Celery('trading', broker='redis://localhost:6379')

@app.task
def run_backtest(run_name, strategy, symbols, ...):
    # Your backtest logic
    return results
    
# In your dashboard
result = run_backtest.delay(run_name, strategy, symbols, ...)
```

**Benefits**:
- ✅ Job persistence (survives restarts)
- ✅ Distributed workers (run backtests on multiple machines)
- ✅ Job retry logic
- ✅ Progress tracking
- ✅ Job prioritization

---

### 2. Real-Time Market Data Caching

**Use Case**: Cache latest candles, signals, positions
```python
import redis
r = redis.Redis(host='localhost', port=6379)

# Cache latest M5 candle for TSLA
r.setex('candle:TSLA:M5', 300, json.dumps(candle_data))  # Expires in 5 min

# Retrieve from cache
cached = r.get('candle:TSLA:M5')
```

**Benefits**:
- ✅ Reduce database queries
- ✅ Sub-millisecond access times
- ✅ Automatic expiration (TTL)
- ✅ Shared across all services

---

### 3. Pub/Sub for Service Communication

**Current**: Services communicate via SQLite bridges

**With Redis Pub/Sub**:
```python
# In marketdata-stream (publisher)
r.publish('signals', json.dumps(signal))

# In automatictrader-worker (subscriber)
pubsub = r.pubsub()
pubsub.subscribe('signals')
for message in pubsub.listen():
    process_signal(message['data'])
```

**Benefits**:
- ✅ Real-time event streaming
- ✅ Decoupled services
- ✅ Multiple subscribers
- ✅ Lower latency than SQLite polling

---

### 4. Session Management for Dashboard

**Use Case**: Store user sessions, running jobs, temporary state
```python
# Store active dashboard session
r.hset('session:12345', mapping={
    'user': 'admin',
    'active_jobs': '3',
    'last_seen': datetime.now().isoformat()
})
r.expire('session:12345', 3600)  # 1 hour TTL
```

---

### 5. Rate Limiting for External APIs

**Use Case**: Prevent exceeding EODHD API limits
```python
def check_rate_limit(api_key, limit=100, window=3600):
    key = f'rate_limit:{api_key}'
    current = r.incr(key)
    if current == 1:
        r.expire(key, window)
    return current <= limit
```

---

## System Architecture with Redis

```
┌─────────────────────────────────────────────────┐
│                                                 │
│  Trading Dashboard (Dash)                       │
│  ├─ Submit backtest → Redis Queue               │
│  └─ Poll job status from Redis                  │
│                                                 │
└────────────────┬────────────────────────────────┘
                 │
                 │ redis://
                 ↓
┌─────────────────────────────────────────────────┐
│                                                 │
│  Redis Server                                   │
│  ├─ Job Queue (Celery broker)                   │
│  ├─ Cache (market data, configs)                │
│  ├─ Pub/Sub (signals, events)                   │
│  └─ Sessions (dashboard state)                  │
│                                                 │
└────────────────┬────────────────────────────────┘
                 │
                 │ Pull jobs
                 ↓
┌─────────────────────────────────────────────────┐
│                                                 │
│  Celery Workers (1-N machines)                  │
│  └─ Execute backtests in parallel               │
│                                                 │
└─────────────────────────────────────────────────┘
```

---

## Implementation Roadmap

### Phase 1: Cache Layer (Low Risk, High Value)

**Install Redis**:
```bash
# On Debian server
sudo apt-get update
sudo apt-get install redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Verify
redis-cli ping  # Should return PONG

# Install Python client
pip install redis
```

**Quick Win Implementation**: Cache strategy configs, market data snapshots
- Estimated effort: 1-2 hours
- Immediate performance boost

**Example Code**:
```python
# Add to your config
REDIS_CONFIG = {
    'host': 'localhost',
    'port': 6379,
    'db': 0
}

# Cache market data
def get_latest_candle(symbol, interval):
    cache_key = f'candle:{symbol}:{interval}'
    cached = redis_client.get(cache_key)
    
    if cached:
        return json.loads(cached)
    
    # Fetch from database
    candle = db.get_latest_candle(symbol, interval)
    
    # Cache for 5 minutes
    redis_client.setex(cache_key, 300, json.dumps(candle))
    return candle
```

---

### Phase 2: Job Queue (Medium Risk, Highest Value)

**Install Celery**:
```bash
pip install celery[redis]
```

**Replace threading**: Migrate dashboard backtest jobs to Celery
- Estimated effort: 4-6 hours
- Massive scalability improvement

**Example Code**:
```python
# trading_dashboard/celery_app.py
from celery import Celery

app = Celery('trading_dashboard')
app.config_from_object({
    'broker_url': 'redis://localhost:6379/0',
    'result_backend': 'redis://localhost:6379/0'
})

@app.task(bind=True)
def run_backtest_task(self, run_name, strategy, symbols, timeframe, period, config_params):
    """Execute backtest in Celery worker."""
    from apps.streamlit.pipeline import execute_pipeline
    from apps.streamlit.state import PipelineConfig, FetchConfig
    
    # Update progress
    self.update_state(state='PROGRESS', meta={'status': 'Fetching data...'})
    
    # Run pipeline
    effective_run_name = execute_pipeline(...)
    
    return {'status': 'success', 'run_name': effective_run_name}

# In dashboard callback
from trading_dashboard.celery_app import run_backtest_task
result = run_backtest_task.delay(run_name, strategy, symbols, timeframe, period, config_params)
job_id = result.id
```

**Start Celery Worker**:
```bash
celery -A trading_dashboard.celery_app worker --loglevel=info
```

---

### Phase 3: Pub/Sub (Medium Risk, Medium Value)

**Replace SQLite bridges**: Use Redis Pub/Sub for signal flow
- Estimated effort: 6-8 hours
- Lower latency, cleaner architecture

**Example Code**:
```python
# In marketdata-stream: publish signals
import redis
r = redis.Redis(host='localhost', port=6379)

def publish_signal(signal):
    r.publish('trading:signals', json.dumps(signal))

# In automatictrader-worker: subscribe to signals
def signal_listener():
    r = redis.Redis(host='localhost', port=6379)
    pubsub = r.pubsub()
    pubsub.subscribe('trading:signals')
    
    for message in pubsub.listen():
        if message['type'] == 'message':
            signal = json.loads(message['data'])
            process_signal(signal)
```

---

## Comparison: Redis vs Alternatives

| Feature | Redis | PostgreSQL | SQLite |
|---------|-------|------------|--------|
| Speed | ⚡ Sub-ms | Medium | Fast (local) |
| Persistence | Optional | ✅ ACID | ✅ ACID |
| Scalability | ✅ Cluster | ✅ | ❌ Single file |
| Pub/Sub | ✅ Native | ✅ LISTEN/NOTIFY | ❌ |
| Job Queue | ✅ (with Celery) | ✅ (with tools) | ❌ |
| Memory Usage | High (in RAM) | Lower | Very low |
| Learning Curve | Medium | High | Low |

---

## Cost-Benefit Analysis

### Benefits
1. **Backtests**: Run 10x more concurrent backtests
2. **Dashboard**: Zero job loss on restart
3. **Latency**: 10-100x faster cache access
4. **Scalability**: Add workers easily
5. **Monitoring**: Better job tracking/debugging

### Costs
1. **Memory**: ~500MB-2GB RAM for Redis
2. **Complexity**: One more service to manage
3. **Learning Curve**: ~1 week to master
4. **Maintenance**: Monitoring, backups

### ROI Assessment
For your scale (personal/small team trading system):
- **High value** if you run many backtests
- **Medium value** for caching/performance
- **Lower value** if satisfied with current speed

---

## Recommended Approach

**Start Small**: Phase 1 (Cache) - Low risk, immediate benefits

**Then Expand**: Phase 2 (Celery) if you need:
- More than 3-5 concurrent backtests
- To run backtests on multiple machines
- Job persistence across dashboard restarts

**Optional**: Phase 3 (Pub/Sub) - SQLite bridges work fine for current scale

---

## Quick Start Commands

```bash
# Installation (Debian)
sudo apt-get update
sudo apt-get install redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Verify installation
redis-cli ping  # Should return PONG

# Python packages
pip install redis celery

# Basic Redis operations
redis-cli
> SET mykey "Hello"
> GET mykey
> EXPIRE mykey 10
> TTL mykey
> KEYS *
```

---

## Redis Configuration

**File**: `/etc/redis/redis.conf`

**Key Settings**:
```conf
# Listen on all interfaces
bind 0.0.0.0

# Set password (optional but recommended)
requirepass your_strong_password

# Persistence options
save 900 1        # Save after 900 sec if at least 1 key changed
save 300 10       # Save after 300 sec if at least 10 keys changed
save 60 10000     # Save after 60 sec if at least 10000 keys changed

# Max memory
maxmemory 2gb
maxmemory-policy allkeys-lru  # Evict least recently used keys
```

---

## Monitoring Redis

```bash
# Check status
sudo systemctl status redis-server

# Connect to Redis CLI
redis-cli

# Monitor commands in real-time
redis-cli MONITOR

# Get server info
redis-cli INFO

# Check memory usage
redis-cli INFO memory

# List all keys (careful in production!)
redis-cli KEYS "*"

# Get specific stats
redis-cli INFO stats
```

---

## Integration with Existing Code

### Current: BacktestService (Threading)
**File**: `trading_dashboard/services/backtest_service.py`

### With Redis: CeleryBacktestService
**New File**: `trading_dashboard/services/celery_backtest_service.py`

**Migration Steps**:
1. Install Redis + Celery
2. Create `celery_app.py` with tasks
3. Update `run_backtest_callback.py` to use Celery tasks
4. Start Celery worker as systemd service
5. Monitor via Flower (Celery monitoring tool)

---

## Production Deployment

### Systemd Service for Celery Worker

**File**: `/etc/systemd/system/celery-worker.service`
```ini
[Unit]
Description=Celery Worker for Trading Dashboard
After=network.target redis-server.service

[Service]
Type=forking
User=mirko
Group=mirko
WorkingDirectory=/opt/trading/traderunner
Environment="PATH=/opt/trading/venv/bin"
ExecStart=/opt/trading/venv/bin/celery -A trading_dashboard.celery_app worker --loglevel=info --detach
ExecStop=/opt/trading/venv/bin/celery -A trading_dashboard.celery_app control shutdown
Restart=always

[Install]
WantedBy=multi-user.target
```

**Enable and start**:
```bash
sudo systemctl enable celery-worker
sudo systemctl start celery-worker
sudo systemctl status celery-worker
```

---

## Resources

### Official Documentation
- Redis: https://redis.io/documentation
- Celery: https://docs.celeryq.dev/
- Redis Python Client: https://redis-py.readthedocs.io/

### Tutorials
- Redis University (free): https://university.redis.com/
- Celery Best Practices: https://docs.celeryq.dev/en/stable/userguide/tasks.html

### Monitoring Tools
- RedisInsight: https://redis.com/redis-enterprise/redis-insight/
- Flower (Celery): https://flower.readthedocs.io/

---

## Decision Checklist

Before implementing Redis, ask:

- [ ] Do I run more than 5 concurrent backtests regularly?
- [ ] Do I need job persistence across dashboard restarts?
- [ ] Do I want to distribute work across multiple machines?
- [ ] Is my dashboard getting slow due to repeated database queries?
- [ ] Am I comfortable managing another service (Redis)?
- [ ] Do I have 1-2GB RAM to spare for Redis?

**If 3+ are "Yes"**: Redis is worth it  
**If 1-2 are "Yes"**: Consider Redis for future  
**If 0 are "Yes"**: Current architecture is sufficient

---

## Next Steps

1. **Evaluate**: Review this document and assess need
2. **Test Locally**: Install Redis on laptop and experiment
3. **Phase 1**: Implement caching for quick wins
4. **Measure**: Track performance improvements
5. **Phase 2**: Add Celery if seeing benefits
6. **Production**: Deploy to Debian server

---

**Notes**: This is a reference document for future consideration. The current threading-based implementation works well for current scale. Redis can be added incrementally when/if the need arises.
