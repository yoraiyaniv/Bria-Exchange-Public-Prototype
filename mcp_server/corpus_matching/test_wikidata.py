from wikidata_tool import WIKIDATA_TOOL_DEFINITION as T, execute_wikidata_tool as fn

def test():
    result = fn({"query": "OpenAI"})
    assert result.get("found"), f"Expected found=True, got: {result}"
    assert result["source"] == "Wikidata"
    entity = result.get("top_entity", {})
    assert entity.get("label")
    print(f"  ✓ {entity['label']}: {entity.get('description', '')[:60]}")

if __name__ == "__main__":
    print(f"Testing: {T['name']}")
    test()
    print("PASS")
