from geonames_tool import TOOL_DEFINITION as T, execute_search_geonames_tool as fn

def test():
    result = fn({"query": "Tokyo", "country": "JP", "feature_class": "P"})
    if "error" in result and "401" in str(result["error"]):
        print("  SKIP — GeoNames 401: enable free webservices at geonames.org/manageaccount")
        return
    assert result.get("found"), f"Expected found=True, got: {result}"
    assert result["source"] == "GeoNames"
    assert len(result["results"]) > 0
    r = result["results"][0]
    assert r.get("name")
    assert r.get("population") is not None
    print(f"  ✓ {r['name']}, {r['country_code']} — pop {r['population']:,}")

if __name__ == "__main__":
    print(f"Testing: {T['name']}")
    test()
    print("PASS")
