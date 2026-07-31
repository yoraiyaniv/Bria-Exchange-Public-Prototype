from guardian_tool import GUARDIAN_TOOL_DEFINITION as T, execute_guardian_tool as fn

def test():
    result = fn({"query": "OpenAI GPT-4 release 2023"})
    assert result.get("found"), f"Expected found=True, got: {result}"
    assert result["source"] == "The Guardian"
    assert len(result["articles"]) > 0
    r = result["articles"][0]
    assert r.get("headline")
    assert r.get("url")
    print(f"  ✓ {r['headline'][:60]}")

if __name__ == "__main__":
    print(f"Testing: {T['name']}")
    test()
    print("PASS")
