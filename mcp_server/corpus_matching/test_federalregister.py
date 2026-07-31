from federalregister_tool import TOOL_DEFINITION as T, execute_search_federal_register_tool as fn

def test():
    result = fn({"query": "clean air emissions standards"})
    assert result.get("found"), f"Expected found=True, got: {result}"
    assert result["source"] == "US Federal Register"
    assert len(result["results"]) > 0
    r = result["results"][0]
    assert r.get("title")
    assert r.get("document_number")
    print(f"  ✓ {r['title'][:60]} ({r['publication_date']})")

if __name__ == "__main__":
    print(f"Testing: {T['name']}")
    test()
    print("PASS")
