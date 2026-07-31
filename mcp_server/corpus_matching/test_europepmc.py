from europepmc_tool import TOOL_DEFINITION as T, execute_search_europepmc_tool as fn

def test():
    result = fn({"query": "semaglutide obesity weight loss randomized"})
    assert result.get("found"), f"Expected found=True, got: {result}"
    assert result["source"] == "Europe PubMed Central"
    assert len(result["results"]) > 0
    r = result["results"][0]
    assert r.get("title")
    assert r.get("id")
    print(f"  ✓ {r['title'][:60]} ({r.get('pub_year', 'n/a')})")

if __name__ == "__main__":
    print(f"Testing: {T['name']}")
    test()
    print("PASS")
