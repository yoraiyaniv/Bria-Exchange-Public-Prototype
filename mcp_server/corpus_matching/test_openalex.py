from openalex_tool import TOOL_DEFINITION as T, execute_search_openalex_tool as fn

def test():
    result = fn({"query": "BERT pre-training deep bidirectional transformers", "from_year": 2018})
    assert result.get("found"), f"Expected found=True, got: {result}"
    assert result["source"] == "OpenAlex"
    assert len(result["results"]) > 0
    r = result["results"][0]
    assert r.get("title")
    assert r.get("citations") is not None
    print(f"  ✓ {r['title'][:60]} — {r['citations']} citations")

if __name__ == "__main__":
    print(f"Testing: {T['name']}")
    test()
    print("PASS")
