from clinicaltrials_tool import CLINICALTRIALS_TOOL_DEFINITION as T, execute_clinicaltrials_tool as fn

def test():
    result = fn({"query": "semaglutide obesity phase 3"})
    assert result.get("found"), f"Expected found=True, got: {result}"
    assert result["source"] == "ClinicalTrials.gov"
    assert len(result["studies"]) > 0
    s = result["studies"][0]
    assert s.get("nct_id")
    assert s.get("title")
    print(f"  ✓ {s['nct_id']}: {s['title'][:60]}")

if __name__ == "__main__":
    print(f"Testing: {T['name']}")
    test()
    print("PASS")
