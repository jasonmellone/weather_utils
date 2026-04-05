import datetime
import weather_utils.abstract as abstract


class NWSProvider(abstract.WeatherProvider):
    def get_daily_data(
        self, lat: float, lon: float, date: datetime.date
    ) -> abstract.HarmonizedWeather:
        # 1. Point-to-Grid lookup
        points_url = f"https://api.weather.gov/points/{lat},{lon}"
        grid_data = self.client.get(points_url).json()
        forecast_url = grid_data["properties"]["forecastHourly"]

        # 2. Get Hourly Forecast
        periods = self.client.get(forecast_url).json()["properties"]["periods"]

        day_periods = [
            p for p in periods if p["startTime"].startswith(date.strftime("%Y-%m-%d"))
        ]

        # Extract features
        temps = [p["temperature"] for p in day_periods]
        window_periods = [
            p
            for p in day_periods
            if 10 <= datetime.datetime.fromisoformat(p["startTime"]).hour <= 12
        ]

        # Logic: Check shortForecast string for keywords
        is_rain = any("rain" in p["shortForecast"].lower() for p in day_periods)
        window_precip = any(
            "rain" in p["shortForecast"].lower() or "snow" in p["shortForecast"].lower()
            for p in window_periods
        )

        return abstract.HarmonizedWeather(
            timestamp=datetime.datetime.combine(date, datetime.time.min),
            temp_max=max(temps) if temps else 0.0,
            temp_min=min(temps) if temps else 0.0,
            is_raining=is_rain,
            window_has_precip=window_precip,
            source_api="NWS",
        )
