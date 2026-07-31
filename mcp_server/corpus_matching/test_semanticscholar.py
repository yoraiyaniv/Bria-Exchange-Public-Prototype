from semanticscholar_tool import SEMANTICSCHOLAR_TOOL_DEFINITION as T, execute_semanticscholar_tool as fn

def test():
    result = fn({"query": "GPT-4 technical report OpenAI 2023"})
    if "error" in result and "429" in str(result["error"]):
        print("  SKIP — Semantic Scholar rate limited (429)")
        return
    assert result.get("found"), f"Expected found=True, got: {result}"
    assert result["source"] == "Semantic Scholar"
    assert len(result["papers"]) > 0
    r = result["papers"][0]
    assert r.get("title")
    assert r.get("paper_id")
    print(f"  ✓ {r['title'][:60]} — {r.get('citation_count', 0)} citations")

if __name__ == "__main__":
    print(f"Testing: {T['name']}")
    test()
    print("PASS")
