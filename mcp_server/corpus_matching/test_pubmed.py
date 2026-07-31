from pubmed_tool import PUBMED_TOOL_DEFINITION as T, execute_pubmed_tool as fn

def test():
    result = fn({"query": "semaglutide weight loss obesity RCT"})
    assert result.get("found"), f"Expected found=True, got: {result}"
    assert "PubMed" in result["source"]
    assert len(result["articles"]) > 0
    r = result["articles"][0]
    assert r.get("pmid")
    assert r.get("title")
    print(f"  ✓ PMID {r['pmid']}: {r['title'][:60]}")

if __name__ == "__main__":
    print(f"Testing: {T['name']}")
    test()
    print("PASS")
