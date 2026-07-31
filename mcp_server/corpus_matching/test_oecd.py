from oecd_tool import OECD_TOOL_DEFINITION as T, execute_oecd_tool as fn

def test():
    result = fn({"indicator": "unemployment", "country_code": "USA", "start_year": 2020, "end_year": 2023})
    assert result.get("found"), f"Expected found=True, got: {result}"
    assert "IMF" in result["source"]
    assert result.get("data") or result.get("countries")
    data = result.get("data") or list(result["countries"].values())[0]
    assert len(data) > 0
    d = data[0]
    assert d.get("year")
    assert d.get("value") is not None
    print(f"  ✓ USA unemployment {d['year']}: {d['value']}%")

if __name__ == "__main__":
    print(f"Testing: {T['name']}")
    test()
    print("PASS")
