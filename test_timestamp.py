import json
from datetime import datetime

# Raw Redis data
raw = '{"windowStart":1763274540.0,"windowEnd":1763274600.0}'
data = json.loads(raw)

print(f"Raw windowStart: {data['windowStart']}")
print(f"Raw windowEnd: {data['windowEnd']}")
print()

# Test direct fromtimestamp (what the code does now)
ts1 = datetime.fromtimestamp(data['windowStart'])
ts2 = datetime.fromtimestamp(data['windowEnd'])
print(f"Direct fromtimestamp (windowStart): {ts1}")
print(f"Direct fromtimestamp (windowEnd): {ts2}")
print()

# Test divided by 1 billion
ts3 = datetime.fromtimestamp(data['windowStart'] / 1_000_000_000)
ts4 = datetime.fromtimestamp(data['windowEnd'] / 1_000_000_000)
print(f"Divided by 1B (windowStart): {ts3}")
print(f"Divided by 1B (windowEnd): {ts4}")
