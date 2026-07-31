from fred_tool import FRED_TOOL_DEFINITION as T, execute_fred_tool as fn, FredClient

def test():
    client = FredClient()
    result = fn({"series_id": "UNRATE", "start_date": "2024-01-01", "end_date": "2024-12-31"}, client=client)
    assert "observations" in result, f"Expected observations, got: {result}"
    assert len(result["observations"]) > 0
    obs = result["observations"][0]
    assert obs.get("value") is not None
    print(f"  ✓ UNRATE {obs['date']}: {obs['value']}")

if __name__ == "__main__":
    print(f"Testing: {T['name']}")
    test()
    print("PASS")
