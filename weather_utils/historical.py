import datetime
import weather_utils.abstract as abstract


class NCEIProvider(abstract.WeatherProvider):
    def __init__(self, user_agent: str, token: str):
        super().__init__(user_agent)
        self.client.headers.update({"token": token})

    def _find_nearest_station(self, lat: float, lon: float) -> str:
        """Finds the nearest GHCND station ID for a given coordinate."""
        url = "https://www.ncei.noaa.gov/cdo-web/api/v2/stations"
        params = {
            "extent": f"{lat - 0.5},{lon - 0.5},{lat + 0.5},{lon + 0.5}",  # 1-degree bounding box
            "datasetid": "GHCND",
            "limit": 5,
        }
        resp = self.client.get(url, params=params).json()
        # Sort by proximity or just take the first result
        stations = resp.get("results", [])
        if not stations:
            raise ValueError("No stations found in this area.")

        for station in stations:
            max_date = datetime.datetime.strptime(station["maxdate"], "%Y-%m-%d")
            ddiff = (datetime.datetime.now() - max_date).days
            if ddiff < 10:
                return station["id"]

        raise NotImplementedError("No valid historical station found")

    def get_daily_data(
        self, lat: float, lon: float, target_date: datetime.date
    ) -> abstract.HarmonizedWeather:
        station_id = self._find_nearest_station(lat, lon)

        url = "https://www.ncei.noaa.gov/cdo-web/api/v2/data"
        params = {
            "datasetid": "GHCND",
            "stationid": station_id,
            "startdate": target_date.isoformat(),
            "enddate": target_date.isoformat(),
            "datatypeid": "TMAX,TMIN,PRCP,SNOW",
            "units": "metric",
            "limit": 25,
        }
        resp = self.client.get(url, params=params).json()
        results = resp.get("results", [])

        data: dict[str, float] = {item["datatype"]: item["value"] for item in results}

        # GHCND stores TMAX/TMIN in tenths of degrees C
        temp_max = self._convert_c_to_f(data.get("TMAX", 0.0) / 10.0)
        temp_min = self._convert_c_to_f(data.get("TMIN", 0.0) / 10.0)

        # PRCP is tenths of mm; SNOW is mm — any positive value means precip occurred
        is_raining = data.get("PRCP", 0.0) > 0.0
        is_snowing = data.get("SNOW", 0.0) > 0.0

        return abstract.HarmonizedWeather(
            timestamp=datetime.datetime.combine(target_date, datetime.time.min),
            temp_max=temp_max,
            temp_min=temp_min,
            is_raining=is_raining,
            is_snowing=is_snowing,
            window_has_precip=None,  # GHCND has no sub-daily resolution
            source_api="NCEI",
        )


class ACISProvider(abstract.WeatherProvider):
    def get_daily_data(
        self, lat: float, lon: float, target_date: datetime.date
    ) -> abstract.HarmonizedWeather:
        url = "https://data.rcc-acis.org/GridData"
        payload = {
            "loc": f"{lon},{lat}",
            "sdate": target_date.isoformat(),
            "edate": target_date.isoformat(),
            "grid": "nrcc-meta",
            # We now request 4 elements: MaxT, MinT, Precip, and Snowfall
            "elems": [
                {"name": "maxt"},
                {"name": "mint"},
                {"name": "pcpn"},
                {"name": "snow"},
            ],
        }

        resp = self.client.post(url, json=payload).json()
        # ACIS returns data as: [["2026-04-01", ["75", "62", "0.00", "0.0"]]]
        day_data = resp["data"][0][1]

        # Parse values, handling 'T' for Trace amounts which often appear in snow data
        precip = 0.0 if day_data[2] == "T" else float(day_data[2])
        snowfall = 0.0 if day_data[3] == "T" else float(day_data[3])

        return abstract.HarmonizedWeather(
            timestamp=datetime.datetime.combine(
                target_date, datetime.datetime.min.time()
            ),
            temp_max=float(day_data[0]),
            temp_min=float(day_data[1]),
            is_raining=precip > 0 and snowfall == 0,  # Simple logic: precip but no snow
            is_snowing=snowfall > 0,
            source_api="ACIS-Gridded",
        )


if __name__ == "__main__":
    pass
