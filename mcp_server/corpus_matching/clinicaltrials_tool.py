"""
Bria Exchange — ClinicalTrials.gov Tool
Searches the ClinicalTrials.gov registry via REST API v2.
Good for: trial phase, status, enrollment numbers, primary endpoints,
          sponsor, and results availability.
"""

import requests

CT_API   = "https://clinicaltrials.gov/api/v2/studies"
TIMEOUT  = 8


CLINICALTRIALS_TOOL_DEFINITION = {
    "name": "search_clinicaltrials",
    "description": (
        "Search ClinicalTrials.gov for registered clinical studies. "
        "Use for verifying claims about trial phase, status, enrollment size, "
        "sponsor, primary endpoints, and whether results have been posted. "
        "Covers trials registered worldwide."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search terms (e.g. 'semaglutide obesity phase 3', 'Moderna mRNA-1273').",
            },
            "status": {
                "type": "string",
                "description": "Filter by status: RECRUITING, COMPLETED, ACTIVE_NOT_RECRUITING, etc. (optional).",
            },
        },
        "required": ["query"],
    },
}


def execute_clinicaltrials_tool(tool_input: dict) -> dict:
    query  = tool_input.get("query", "")
    status = tool_input.get("status")

    if not query:
        return {"error": "query is required"}

    params: dict = {
        "query.term": query,
        "pageSize":   5,
        "format":     "json",
        "fields":     "NCTId,BriefTitle,OverallStatus,Phase,EnrollmentCount,Condition,InterventionName,StartDate,PrimaryCompletionDate,HasResults",
    }
    if status:
        params["filter.overallStatus"] = status

    try:
        resp = requests.get(CT_API, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        data    = resp.json()
        studies = data.get("studies", [])

        if not studies:
            return {
                "found":   False,
                "query":   query,
                "message": f"No clinical trials found for '{query}'.",
                "source":  "ClinicalTrials.gov",
            }

        results = []
        for s in studies:
            proto = s.get("protocolSection", {})
            ident = proto.get("identificationModule", {})
            status_mod = proto.get("statusModule", {})
            design = proto.get("designModule", {})
            desc   = proto.get("descriptionModule", {})
            results.append({
                "nct_id":     ident.get("nctId"),
                "title":      ident.get("briefTitle"),
                "status":     status_mod.get("overallStatus"),
                "phase":      (design.get("phases") or [None])[0],
                "enrollment": design.get("enrollmentInfo", {}).get("count"),
                "start_date": status_mod.get("startDateStruct", {}).get("date"),
                "completion": status_mod.get("primaryCompletionDateStruct", {}).get("date"),
                "has_results": s.get("hasResults", False),
                "url":        f"https://clinicaltrials.gov/study/{ident.get('nctId')}",
            })

        return {
            "found":   True,
            "query":   query,
            "studies": results,
            "source":  "ClinicalTrials.gov",
        }

    except requests.RequestException as exc:
        return {"error": f"ClinicalTrials request failed: {exc}"}
