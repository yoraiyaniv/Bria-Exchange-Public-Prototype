from openmeteo_tool import TOOL_DEFINITION as T, execute_get_weather_data_tool as fn

def test():
    result = fn({
        "latitude": 40.71, "longitude": -74.01,
        "start_date": "2025-01-01", "end_date": "2025-01-07",
    })
    assert result.get("found"), f"Expected found=True, got: {result}"
    assert result["source"] == "Open-Meteo"
    assert len(result["data"]) > 0
    d = result["data"][0]
    assert d.get("date")
    print(f"  ✓ NYC {d['date']} max temp: {d.get('temperature_2m_max')}°C")

if __name__ == "__main__":
    print(f"Testing: {T['name']}")
    test()
    print("PASS")
