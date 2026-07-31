from census_tool import CENSUS_TOOL_DEFINITION as T, execute_census_tool as fn

def test():
    result = fn({"variable": "population", "geography": "us", "year": 2022})
    assert result.get("found"), f"Expected found=True, got: {result}"
    assert result["source"] == "US Census Bureau (ACS 5-Year)"
    assert len(result["results"]) > 0
    r = result["results"][0]
    assert r.get("value") is not None
    print(f"  ✓ US population 2022: {int(r['value']):,}")

if __name__ == "__main__":
    print(f"Testing: {T['name']}")
    test()
    print("PASS")
