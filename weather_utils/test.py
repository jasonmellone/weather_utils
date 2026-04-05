import datetime
import json
import weather_utils.forecast as forecast_module

# import cap_rate.data.weather.forecast
import weather_utils.historical as historical_module
# import cap_rate.data.weather.historical as historical_module


def run_weather_test(
    provider: historical_module.abstract.WeatherProvider,
    name: str,
    lat: float,
    lon: float,
    target_date: datetime.date,
) -> historical_module.abstract.HarmonizedWeather | None:
    print(f"--- Testing {name} Provider ---")

    result = provider.get_daily_data(lat, lon, target_date)
    print(json.dumps(result.model_dump(), indent=2, default=str))
    assert isinstance(result.temp_max, float)
    assert isinstance(result.is_raining, bool)
    assert isinstance(result.is_snowing, bool)
    print(f"✅ {name} test passed validation.\n")
    return result


def main() -> None:
    nws = forecast_module.NWSProvider(user_agent="QuantTest/1.0")
    run_weather_test(nws, "NWS_Forecast", 24.7136, -81.0904, datetime.date.today())

    ncei = historical_module.NCEIProvider(
        user_agent="QuantApp/1.0", token="tokOSSybwgDjalVyDrVCZiGWziqJomsM"
    )

    data = ncei.get_daily_data(40.9259, -73.8271, datetime.date(2026, 2, 24))
    print(f"Verified NCEI for {data.source_api}:")
    print(
        f"Max Temp: {data.temp_max}F | Rain: {data.is_raining} | Snow: {data.is_snowing}"
    )

    acis = historical_module.ACISProvider()
    run_weather_test(
        acis, "ACIS_Historical_Snow", 42.8864, -78.8784, datetime.date(2024, 1, 13)
    )
    run_weather_test(
        acis, "ACIS_Historical_Rain", 40.9259, -73.8271, datetime.date(2023, 9, 29)
    )


if __name__ == "__main__":
    main()
