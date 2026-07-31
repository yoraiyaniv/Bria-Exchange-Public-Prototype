from bls_tool import BLS_TOOL_DEFINITION as T, execute_bls_tool as fn

def test():
    result = fn({"series_id": "unemployment", "start_year": 2024, "end_year": 2025})
    if "error" in result:
        print(f"  SKIP — BLS API unreachable: {result['error']}")
        return
    assert result.get("found"), f"Expected found=True, got: {result}"
    assert result["source"] == "Bureau of Labor Statistics (BLS)"
    assert len(result["data"]) > 0
    d = result["data"][0]
    assert d.get("year")
    assert d.get("value") is not None
    print(f"  ✓ Unemployment {d['year']}: {d['value']}%")

if __name__ == "__main__":
    print(f"Testing: {T['name']}")
    test()
    print("PASS")
