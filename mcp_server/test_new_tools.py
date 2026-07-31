"""
Quick smoke test — one real claim per new tool.
Run: uv run python test_new_tools.py
"""

import json
from corpus_matching.arxiv_tool       import TOOL_DEFINITION as ARXIV_DEF,          execute_search_arxiv_tool
from corpus_matching.openalex_tool    import TOOL_DEFINITION as OPENALEX_DEF,        execute_search_openalex_tool
from corpus_matching.europepmc_tool   import TOOL_DEFINITION as EUROPEPMC_DEF,       execute_search_europepmc_tool
from corpus_matching.bls_tool         import BLS_TOOL_DEFINITION,                    execute_bls_tool
from corpus_matching.census_tool      import CENSUS_TOOL_DEFINITION,                 execute_census_tool
from corpus_matching.oecd_tool        import OECD_TOOL_DEFINITION,                   execute_oecd_tool
from corpus_matching.courtlistener_tool   import TOOL_DEFINITION as CL_DEF,          execute_search_courtlistener_tool
from corpus_matching.federalregister_tool import TOOL_DEFINITION as FR_DEF,          execute_search_federal_register_tool
from corpus_matching.openmeteo_tool   import TOOL_DEFINITION as METEO_DEF,           execute_get_weather_data_tool
from corpus_matching.geonames_tool    import TOOL_DEFINITION as GEO_DEF,             execute_search_geonames_tool
from corpus_matching.wikipedia_tool   import TOOL_DEFINITION as WIKI_DEF,            execute_search_wikipedia_tool

TESTS = [
    (
        "arXiv — attention is all you need paper",
        execute_search_arxiv_tool,
        {"query": "attention is all you need transformer", "category": "cs.LG", "max_results": 3},
    ),
    (
        "OpenAlex — GPT-4 paper citations",
        execute_search_openalex_tool,
        {"query": "GPT-4 technical report OpenAI", "from_year": 2023},
    ),
    (
        "Europe PMC — semaglutide weight loss",
        execute_search_europepmc_tool,
        {"query": "semaglutide obesity weight loss randomized", "source": "MED"},
    ),
    (
        "BLS — US unemployment rate",
        execute_bls_tool,
        {"series_id": "unemployment", "start_year": 2024, "end_year": 2025},
    ),
    (
        "Census — US median household income",
        execute_census_tool,
        {"variable": "median_income", "geography": "state", "state_fips": "06", "year": 2022},
    ),
    (
        "OECD — US GDP per capita",
        execute_oecd_tool,
        {"indicator": "gdp_per_capita", "country_code": "USA", "start_year": 2020, "end_year": 2023},
    ),
    (
        "CourtListener — Roe v Wade",
        execute_search_courtlistener_tool,
        {"query": "Roe v Wade abortion", "court": "scotus"},
    ),
    (
        "Federal Register — EPA clean air rule",
        execute_search_federal_register_tool,
        {"query": "clean air emissions standards", "type": "Rule"},
    ),
    (
        "Open-Meteo — NYC temperatures March 2025",
        execute_get_weather_data_tool,
        {"latitude": 40.71, "longitude": -74.01, "start_date": "2025-03-01", "end_date": "2025-03-07"},
    ),
    (
        "GeoNames — Tel Aviv population",
        execute_search_geonames_tool,
        {"query": "Tel Aviv", "country": "IL", "feature_class": "P"},
    ),
    (
        "Wikipedia — Large language model",
        execute_search_wikipedia_tool,
        {"query": "large language model"},
    ),
]


def run():
    passed = 0
    failed = 0
    for label, fn, inputs in TESTS:
        print(f"\n{'─'*60}")
        print(f"  {label}")
        print(f"  input: {json.dumps(inputs)}")
        try:
            result = fn(inputs)
            if "error" in result:
                print(f"  ✗ ERROR: {result['error']}")
                failed += 1
            else:
                found = result.get("found", True)
                source = result.get("source", "?")
                # Print first meaningful key
                preview_keys = ["studies", "results", "data", "title", "geonames", "summary",
                                "result", "opinions", "documents", "data"]
                preview = next((result[k] for k in preview_keys if k in result), None)
                count = len(preview) if isinstance(preview, list) else ("1 result" if preview else "—")
                print(f"  {'✓' if found else '~'} found={found} | source={source} | results={count}")
                passed += 1
        except Exception as e:
            print(f"  ✗ EXCEPTION: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"  {passed}/{passed+failed} tools passed")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    run()
