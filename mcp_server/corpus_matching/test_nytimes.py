import os
from nytimes_tool import NYTIMES_TOOL_DEFINITION as T, execute_nytimes_tool as fn

def test():
    if not os.environ.get("NYTIMES_API_KEY"):
        print("  SKIP — NYTIMES_API_KEY not set")
        return
    result = fn({"query": "Federal Reserve interest rate 2024"})
    assert result.get("found"), f"Expected found=True, got: {result}"
    assert result["source"] == "New York Times"
    assert len(result["articles"]) > 0
    r = result["articles"][0]
    assert r.get("headline")
    print(f"  ✓ {r['headline'][:60]}")

if __name__ == "__main__":
    print(f"Testing: {T['name']}")
    test()
    print("PASS")
