from crossref_tool import CROSSREF_TOOL_DEFINITION as T, execute_crossref_tool as fn

def test():
    result = fn({"query": "attention is all you need Vaswani 2017"})
    assert result.get("found"), f"Expected found=True, got: {result}"
    assert result["source"] == "CrossRef"
    assert len(result["results"]) > 0
    r = result["results"][0]
    assert r.get("doi")
    assert r.get("title")
    print(f"  ✓ {r['title'][:60]} (DOI: {r['doi']})")

if __name__ == "__main__":
    print(f"Testing: {T['name']}")
    test()
    print("PASS")
