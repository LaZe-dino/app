"""Run the SQL schema against Supabase using the REST SQL execution endpoint."""
import requests
import sys

SUPABASE_URL = "https://wmsyvahmriucdyykpuau.supabase.co"
SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indtc3l2YWhtcml1Y2R5eWtwdWF1Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTU1MzY0MiwiZXhwIjoyMDg3MTI5NjQyfQ.07mnOGyicHSbDuBjPXBvxtzHkKRqxvJd1TPbCwFnDnA"

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

# Split schema into individual statements and run each
with open("supabase/schema.sql", "r", encoding="utf-8") as f:
    raw = f.read()

# Remove comments and split by semicolons
statements = []
current = []
for line in raw.split("\n"):
    stripped = line.strip()
    if stripped.startswith("--") or not stripped:
        continue
    current.append(line)
    if stripped.endswith(";"):
        stmt = "\n".join(current).strip()
        if stmt:
            statements.append(stmt)
        current = []

print(f"Found {len(statements)} SQL statements to execute")

# Use the Supabase SQL query endpoint
sql_url = f"{SUPABASE_URL}/rest/v1/rpc/"

# We need to run SQL directly - use the pg_query approach via a custom function
# First, let's try creating tables one by one via the REST API
# Actually, Supabase has a direct SQL execution via the management API

# Try the query endpoint that PostgREST exposes for RPC
for i, stmt in enumerate(statements):
    # Skip extension creation (already enabled in Supabase)
    if "CREATE EXTENSION" in stmt:
        print(f"  [{i+1}] Skipping extension (pre-enabled in Supabase)")
        continue
    
    # Skip CREATE POLICY if it might conflict
    desc = stmt[:80].replace("\n", " ")
    print(f"  [{i+1}] {desc}...")

print("\n" + "="*60)
print("SQL statements prepared. Since Supabase REST API doesn't")
print("support raw SQL execution directly, you need to run the")
print("schema via the Supabase Dashboard SQL Editor.")
print("")
print("But let me test if tables already exist or create them")
print("using the supabase-py client instead...")
print("="*60)

# Use supabase-py to test
from supabase import create_client
client = create_client(SUPABASE_URL, SERVICE_KEY)

# Test if tables exist by trying to query them
tables_to_check = ["users", "portfolio", "trade_signals", "reports", "hft_trades", "hft_snapshots"]
for table in tables_to_check:
    try:
        result = client.table(table).select("*").limit(1).execute()
        print(f"  [OK] Table '{table}' exists ({len(result.data)} rows)")
    except Exception as e:
        err = str(e)
        if "does not exist" in err or "404" in err or "relation" in err:
            print(f"  [MISSING] Table '{table}' does not exist yet")
        else:
            print(f"  [ERROR] Table '{table}': {err[:100]}")

print("\nDone. If tables are missing, paste schema.sql into Supabase SQL Editor.")
