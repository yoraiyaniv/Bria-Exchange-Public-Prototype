from edgar_tool import EDGAR_TOOL_DEFINITION as T, execute_edgar_tool as fn, EdgarClient

def test():
    client = EdgarClient()
    result = fn({"ticker": "AAPL", "concept": "Revenues", "form": "10-K"}, client=client)
    assert result.get("facts"), f"Expected facts, got: {list(result.keys())}"
    assert len(result["facts"]) > 0
    f = result["facts"][0]
    assert f.get("value_raw") is not None
    print(f"  ✓ AAPL Revenues {f['period_end']}: ${f['value_raw']:,.0f}")

if __name__ == "__main__":
    print(f"Testing: {T['name']}")
    test()
    print("PASS")
