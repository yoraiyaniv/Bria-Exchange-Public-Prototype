from arxiv_tool import TOOL_DEFINITION as T, execute_search_arxiv_tool as fn
import json

def test():
    result = fn({"query": "attention is all you need transformer", "max_results": 3})
    assert result.get("found"), f"Expected found=True, got: {result}"
    assert result["source"] == "arXiv"
    assert len(result["results"]) > 0
    r = result["results"][0]
    assert r.get("title")
    assert r.get("arxiv_id")
    print(f"  ✓ {r['title'][:60]} ({r['arxiv_id']})")

if __name__ == "__main__":
    print(f"Testing: {T['name']}")
    test()
    print("PASS")
