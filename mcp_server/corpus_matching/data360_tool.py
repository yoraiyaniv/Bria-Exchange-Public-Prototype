"""
Bria Exchange — World Bank Data360 Tool
Searches World Bank indicators by keyword and fetches data.
Unlike get_worldbank_data (which requires a known indicator code), this tool
lets you SEARCH for indicators by topic across 20,000+ indicators.
No API key required — World Bank APIs are free.
"""

import requests

TIMEOUT = 10
WB_API = "https://api.worldbank.org/v2"

# Large mapping of common search terms to World Bank indicator codes.
# This is the key value-add: the model can search by topic instead of
# needing to know the exact indicator code.
INDICATOR_SEARCH: dict[str, tuple[str, str]] = {
    # Education
    "literacy rate": ("SE.ADT.LITR.ZS", "Literacy rate, adult total (% of people ages 15+)"),
    "literacy": ("SE.ADT.LITR.ZS", "Literacy rate, adult total (% of people ages 15+)"),
    "school enrollment primary": ("SE.PRM.ENRR", "School enrollment, primary (% gross)"),
    "school enrollment secondary": ("SE.SEC.ENRR", "School enrollment, secondary (% gross)"),
    "school enrollment tertiary": ("SE.TER.ENRR", "School enrollment, tertiary (% gross)"),
    "education expenditure": ("SE.XPD.TOTL.GD.ZS", "Government expenditure on education (% of GDP)"),
    "pupil teacher ratio": ("SE.PRM.ENRL.TC.ZS", "Pupil-teacher ratio, primary"),
    "years of schooling": ("SE.SCH.LIFE", "Expected years of schooling"),
    # Health
    "life expectancy": ("SP.DYN.LE00.IN", "Life expectancy at birth, total (years)"),
    "life expectancy male": ("SP.DYN.LE00.MA.IN", "Life expectancy at birth, male (years)"),
    "life expectancy female": ("SP.DYN.LE00.FE.IN", "Life expectancy at birth, female (years)"),
    "infant mortality": ("SP.DYN.IMRT.IN", "Mortality rate, infant (per 1,000 live births)"),
    "child mortality": ("SH.DYN.MORT", "Mortality rate, under-5 (per 1,000 live births)"),
    "maternal mortality": ("SH.STA.MMRT", "Maternal mortality ratio (per 100,000 live births)"),
    "hospital beds": ("SH.MED.BEDS.ZS", "Hospital beds (per 1,000 people)"),
    "physicians": ("SH.MED.PHYS.ZS", "Physicians (per 1,000 people)"),
    "nurses": ("SH.MED.NUMW.P3", "Nurses and midwives (per 1,000 people)"),
    "health expenditure": ("SH.XPD.CHEX.GD.ZS", "Current health expenditure (% of GDP)"),
    "immunization measles": ("SH.IMM.MEAS", "Immunization, measles (% children 12-23 months)"),
    "immunization dpt": ("SH.IMM.IDPT", "Immunization, DPT (% children 12-23 months)"),
    "hiv prevalence": ("SH.DYN.AIDS.ZS", "Prevalence of HIV, total (% of population ages 15-49)"),
    "tuberculosis": ("SH.TBS.INCD", "Incidence of tuberculosis (per 100,000 people)"),
    "malaria": ("SH.STA.MALR", "Malaria cases reported"),
    "obesity": ("SH.STA.OWAD.ZS", "Prevalence of overweight, adults (% of adults)"),
    "stunting": ("SH.STA.STNT.ZS", "Prevalence of stunting among children"),
    "water access": ("SH.H2O.BASW.ZS", "People using basic drinking water services (%)"),
    "sanitation": ("SH.STA.BASS.ZS", "People using basic sanitation services (%)"),
    # Demographics
    "population": ("SP.POP.TOTL", "Population, total"),
    "population growth": ("SP.POP.GROW", "Population growth (annual %)"),
    "urban population": ("SP.URB.TOTL.IN.ZS", "Urban population (% of total)"),
    "fertility rate": ("SP.DYN.TFRT.IN", "Fertility rate, total (births per woman)"),
    "birth rate": ("SP.DYN.CBRT.IN", "Birth rate, crude (per 1,000 people)"),
    "death rate": ("SP.DYN.CDRT.IN", "Death rate, crude (per 1,000 people)"),
    "population density": ("EN.POP.DNST", "Population density (people per sq. km)"),
    "life expectancy at birth": ("SP.DYN.LE00.IN", "Life expectancy at birth, total"),
    "median age": ("SP.POP.AG00.MA.IN", "Population ages 0-14 (% of total)"),
    "refugee population": ("SM.POP.REFG", "Refugee population by country of asylum"),
    "net migration": ("SM.POP.NETM", "Net migration"),
    # Economy
    "gdp": ("NY.GDP.MKTP.CD", "GDP (current US$)"),
    "gdp growth": ("NY.GDP.MKTP.KD.ZG", "GDP growth (annual %)"),
    "gdp per capita": ("NY.GDP.PCAP.CD", "GDP per capita (current US$)"),
    "gdp per capita ppp": ("NY.GDP.PCAP.PP.CD", "GDP per capita, PPP (current intl $)"),
    "gni per capita": ("NY.GNP.PCAP.CD", "GNI per capita (current US$)"),
    "inflation": ("FP.CPI.TOTL.ZG", "Inflation, consumer prices (annual %)"),
    "unemployment": ("SL.UEM.TOTL.ZS", "Unemployment, total (% of labor force)"),
    "poverty": ("SI.POV.DDAY", "Poverty headcount ratio at $2.15/day (%)"),
    "poverty rate": ("SI.POV.DDAY", "Poverty headcount ratio at $2.15/day (%)"),
    "gini": ("SI.POV.GINI", "Gini index"),
    "gini index": ("SI.POV.GINI", "Gini index"),
    "income inequality": ("SI.POV.GINI", "Gini index"),
    "current account": ("BN.CAB.XOKA.GD.ZS", "Current account balance (% of GDP)"),
    "government debt": ("GC.DOD.TOTL.GD.ZS", "Central government debt (% of GDP)"),
    "tax revenue": ("GC.TAX.TOTL.GD.ZS", "Tax revenue (% of GDP)"),
    "government expenditure": ("GC.XPN.TOTL.GD.ZS", "Expense (% of GDP)"),
    "interest rate": ("FR.INR.LEND", "Lending interest rate (%)"),
    "exchange rate": ("PA.NUS.FCRF", "Official exchange rate (LCU per US$)"),
    # Trade & Investment
    "trade": ("TG.VAL.TOTL.GD.ZS", "Merchandise trade (% of GDP)"),
    "exports": ("NE.EXP.GNFS.ZS", "Exports of goods and services (% of GDP)"),
    "imports": ("NE.IMP.GNFS.ZS", "Imports of goods and services (% of GDP)"),
    "fdi": ("BX.KLT.DINV.WD.GD.ZS", "Foreign direct investment, net inflows (% of GDP)"),
    "foreign direct investment": ("BX.KLT.DINV.WD.GD.ZS", "FDI net inflows (% of GDP)"),
    "remittances": ("BX.TRF.PWKR.DT.GD.ZS", "Personal remittances, received (% of GDP)"),
    "tourism": ("ST.INT.ARVL", "International tourism, number of arrivals"),
    "tourism receipts": ("ST.INT.RCPT.CD", "International tourism, receipts (current US$)"),
    # Energy & Environment
    "co2 emissions": ("EN.ATM.CO2E.PC", "CO2 emissions (metric tons per capita)"),
    "co2": ("EN.ATM.CO2E.PC", "CO2 emissions (metric tons per capita)"),
    "renewable energy": ("EG.FEC.RNEW.ZS", "Renewable energy consumption (% of total)"),
    "electricity access": ("EG.ELC.ACCS.ZS", "Access to electricity (% of population)"),
    "energy use": ("EG.USE.PCAP.KG.OE", "Energy use (kg of oil equivalent per capita)"),
    "forest area": ("AG.LND.FRST.ZS", "Forest area (% of land area)"),
    "arable land": ("AG.LND.ARBL.ZS", "Arable land (% of land area)"),
    "freshwater": ("ER.H2O.FWTL.ZS", "Annual freshwater withdrawals (% of internal)"),
    "pm2.5": ("EN.ATM.PM25.MC.M3", "PM2.5 air pollution (micrograms per cubic meter)"),
    "air pollution": ("EN.ATM.PM25.MC.M3", "PM2.5 air pollution"),
    # Technology & Infrastructure
    "internet users": ("IT.NET.USER.ZS", "Individuals using the Internet (% of population)"),
    "mobile subscriptions": ("IT.CEL.SETS.P2", "Mobile cellular subscriptions (per 100 people)"),
    "broadband": ("IT.NET.BBND.P2", "Fixed broadband subscriptions (per 100 people)"),
    "research expenditure": ("GB.XPD.RSDV.GD.ZS", "R&D expenditure (% of GDP)"),
    "patent applications": ("IP.PAT.RESD", "Patent applications, residents"),
    "high tech exports": ("TX.VAL.TECH.MF.ZS", "High-technology exports (% of manufactured exports)"),
    # Labor
    "labor force participation": ("SL.TLF.CACT.ZS", "Labor force participation rate (% of population 15+)"),
    "employment agriculture": ("SL.AGR.EMPL.ZS", "Employment in agriculture (% of total)"),
    "employment industry": ("SL.IND.EMPL.ZS", "Employment in industry (% of total)"),
    "employment services": ("SL.SRV.EMPL.ZS", "Employment in services (% of total)"),
    "youth unemployment": ("SL.UEM.1524.ZS", "Unemployment, youth total (% 15-24)"),
    "female labor": ("SL.TLF.CACT.FE.ZS", "Labor force participation rate, female (%)"),
    # Military & Governance
    "military expenditure": ("MS.MIL.XPND.GD.ZS", "Military expenditure (% of GDP)"),
    "military spending": ("MS.MIL.XPND.GD.ZS", "Military expenditure (% of GDP)"),
    "armed forces": ("MS.MIL.TOTL.P1", "Armed forces personnel, total"),
    # Agriculture
    "agriculture value added": ("NV.AGR.TOTL.ZS", "Agriculture, value added (% of GDP)"),
    "cereal yield": ("AG.YLD.CREL.KG", "Cereal yield (kg per hectare)"),
    "food production": ("AG.PRD.FOOD.XD", "Food production index"),
    # Industry
    "manufacturing": ("NV.IND.MANF.ZS", "Manufacturing, value added (% of GDP)"),
    "industry value added": ("NV.IND.TOTL.ZS", "Industry, value added (% of GDP)"),
    "services value added": ("NV.SRV.TOTL.ZS", "Services, value added (% of GDP)"),
}


TOOL_DEFINITION = {
    "name": "search_data360",
    "description": (
        "Search World Bank Data360 for development indicators by keyword, then fetch data. "
        "Unlike get_worldbank_data which requires a known indicator code, this tool lets you "
        "SEARCH for indicators by topic (e.g. 'literacy rate', 'hospital beds', 'renewable energy'). "
        "Covers 20,000+ indicators across all countries."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Search term for indicators (e.g. 'renewable energy consumption', "
                    "'literacy rate female', 'hospital beds per capita')."
                ),
            },
            "country": {
                "type": "string",
                "description": (
                    "ISO alpha-2 or alpha-3 country code (e.g. 'US', 'CHN', 'GBR'). "
                    "If omitted, returns data for all countries."
                ),
            },
            "indicator": {
                "type": "string",
                "description": (
                    "Specific World Bank indicator code if already known "
                    "(e.g. 'SE.ADT.LITR.ZS'). Skips search and fetches data directly."
                ),
            },
            "year": {
                "type": "integer",
                "description": "Specific year to filter results.",
            },
        },
        "required": ["query"],
    },
}


def _search_indicators(query: str) -> list[tuple[str, str]]:
    """Search the indicator mapping for matches."""
    query_lower = query.lower()
    words = query_lower.split()

    # Exact key match first
    if query_lower in INDICATOR_SEARCH:
        code, name = INDICATOR_SEARCH[query_lower]
        return [(code, name)]

    # Score-based matching: count how many query words appear in each key
    scored = []
    for key, (code, name) in INDICATOR_SEARCH.items():
        score = sum(1 for w in words if w in key or w in name.lower())
        if score > 0:
            scored.append((score, code, name))

    scored.sort(key=lambda x: -x[0])
    return [(code, name) for _, code, name in scored[:5]]


def execute_data360_tool(tool_input: dict) -> dict:
    query = tool_input.get("query", "").strip()
    country = tool_input.get("country", "").strip().upper() or "all"
    indicator = tool_input.get("indicator", "").strip()
    year = tool_input.get("year")

    if not query and not indicator:
        return {"error": "query or indicator is required"}

    try:
        # If indicator code provided directly, skip search
        if indicator:
            matches = [(indicator, indicator)]
        else:
            matches = _search_indicators(query)

        if not matches:
            return {
                "found": False,
                "query": query,
                "matching_indicators": [],
                "message": (
                    f"No matching indicator found for '{query}'. "
                    "Try more specific terms or provide the indicator code directly."
                ),
                "source": "World Bank Data360",
            }

        # Fetch data for the best matching indicator
        best_code, best_name = matches[0]

        params = {"format": "json", "per_page": 20}
        if year:
            params["date"] = str(year)
        else:
            params["mrv"] = 10  # most recent 10 values

        url = f"{WB_API}/country/{country}/indicator/{best_code}"
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        raw = resp.json()

        if not isinstance(raw, list) or len(raw) < 2 or not raw[1]:
            return {
                "found": False,
                "query": query,
                "indicator_code": best_code,
                "indicator_name": best_name,
                "matching_indicators": [
                    {"code": c, "name": n} for c, n in matches
                ],
                "message": f"No data available for indicator {best_code} ({country}).",
                "source": "World Bank Data360",
            }

        data = []
        for entry in raw[1]:
            val = entry.get("value")
            if val is None:
                continue
            data.append({
                "year": entry.get("date", ""),
                "value": val,
                "country": entry.get("country", {}).get("value", ""),
            })

        return {
            "found": bool(data),
            "query": query,
            "indicator_code": best_code,
            "indicator_name": best_name,
            "country": country,
            "data": data,
            "matching_indicators": [
                {"code": c, "name": n} for c, n in matches
            ],
            "source": "World Bank Data360",
        }

    except requests.RequestException as exc:
        return {"error": f"World Bank API request failed: {exc}"}
    except Exception as exc:
        return {"error": f"Data360 error: {exc}"}


if __name__ == "__main__":
    result = execute_data360_tool({
        "query": "literacy rate",
        "country": "USA",
    })
    import json
    print(json.dumps(result, indent=2))
