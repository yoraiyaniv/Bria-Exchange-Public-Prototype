from wikipedia_tool import TOOL_DEFINITION as T, execute_search_wikipedia_tool as fn

def test():
    result = fn({"query": "large language model"})
    assert result.get("found"), f"Expected found=True, got: {result}"
    assert result["source"] == "Wikipedia"
    assert result.get("title")
    assert result.get("summary")
    print(f"  ✓ {result['title']}: {result['summary'][:80]}...")

if __name__ == "__main__":
    print(f"Testing: {T['name']}")
    test()
    print("PASS")
