import pandas as pd

orders = pd.read_csv('/tmp/hood_deployed_orders.csv')
print(f"Total orders: {len(orders)}\n")

# Parse timestamps with UTC
orders['valid_from'] = pd.to_datetime(orders['valid_from'], utc=True)
orders['valid_to'] = pd.to_datetime(orders['valid_to'], utc=True)

# Calculate duration in minutes
orders['duration_min'] = (orders['valid_to'] - orders['valid_from']).dt.total_seconds() / 60

print("Duration Statistics (minutes):")
print(f"  Mean:   {orders['duration_min'].mean():.2f}")
print(f"  Median: {orders['duration_min'].median():.2f}")
print(f"  Min:    {orders['duration_min'].min():.2f}")
print(f"  Max:    {orders['duration_min'].max():.2f}")
print(f"  Std:    {orders['duration_min'].std():.2f}\n")

# Check for ~5 minute windows (one_bar policy)
five_min_count = ((orders['duration_min'] >= 4.9) & (orders['duration_min'] <= 5.1)).sum()
print(f"Orders with ~5 minute duration: {five_min_count}/{len(orders)} ({100*five_min_count/len(orders):.1f}%)\n")

# Distribution
print("Duration Distribution:")
print(orders['duration_min'].value_counts().sort_index())

print("\nFirst 10 orders:")
print(orders[['symbol', 'side', 'valid_from', 'valid_to', 'duration_min']].head(10).to_string(index=False))

# Success check
if five_min_count == len(orders):
    print("\n✅ SUCCESS: All orders have 5-minute validity windows!")
else:
    print(f"\n⚠️ WARNING: {len(orders) - five_min_count} orders do not have 5-minute windows")
