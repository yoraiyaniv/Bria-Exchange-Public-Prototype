from courtlistener_tool import TOOL_DEFINITION as T, execute_search_courtlistener_tool as fn

def test():
    result = fn({"query": "Roe v Wade abortion", "court": "scotus"})
    assert result.get("found"), f"Expected found=True, got: {result}"
    assert result["source"] == "CourtListener"
    assert len(result["results"]) > 0
    r = result["results"][0]
    assert r.get("case_name")
    print(f"  ✓ {r['case_name']} ({r.get('date_filed', 'n/a')})")

if __name__ == "__main__":
    print(f"Testing: {T['name']}")
    test()
    print("PASS")
