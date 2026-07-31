from worldbank_tool import WORLDBANK_TOOL_DEFINITION as T, execute_worldbank_tool as fn

def test():
    result = fn({"country_code": "US", "indicator": "gdp", "year_from": 2020, "year_to": 2023})
    assert result.get("found"), f"Expected found=True, got: {result}"
    assert result["source"] == "World Bank Open Data"
    assert len(result["data"]) > 0
    d = result["data"][0]
    assert d.get("year")
    assert d.get("value") is not None
    print(f"  ✓ US GDP {d['year']}: ${d['value']:,.0f}")

if __name__ == "__main__":
    print(f"Testing: {T['name']}")
    test()
    print("PASS")
