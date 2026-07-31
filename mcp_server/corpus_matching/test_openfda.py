from openfda_tool import OPENFDA_TOOL_DEFINITION as T, execute_openfda_tool as fn

def test():
    result = fn({"query": "ozempic", "endpoint": "drug_label"})
    assert result.get("found"), f"Expected found=True, got: {result}"
    assert "OpenFDA" in result["source"]
    assert len(result["results"]) > 0
    r = result["results"][0]
    assert r.get("brand_name")
    print(f"  ✓ {r['brand_name']} ({r.get('generic_name', 'n/a')})")

if __name__ == "__main__":
    print(f"Testing: {T['name']}")
    test()
    print("PASS")
