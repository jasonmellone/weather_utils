import functools
import time
import traceback
import typing

import pandas as pd
import requests

API = "e1f10a1e78da46f5b10a1e78da96f525"


class WeatherForecast:
    def __init__(self) -> None:
        self.API: str = (
            "e1f10a1e78da46f5b10a1e78da96f525"  # "eac68c066097607b3d8de4e480067a01"
        )
        # https://openweathermap.org/forecast5
        # https://home.openweathermap.org/api_keys
        # https://openweathermap.org/api


class HistoricalWeatherData:
    def __init__(self, db: typing.Any, connect: bool = True) -> None:
        """Initialize with a database connection provided by the caller.

        Args:
            db: Database wrapper with ``connect()`` and ``engine`` attributes.
            connect: Whether to call ``db.connect()`` during initialization.
        """
        self.db = db
        if connect:
            self.db.connect()
        self.table: str = "WundergroundHistorical"
        self.pre_existing_dates: list[typing.Any] = []

    def create_datetime_from_column(
        self, row: pd.Series, column: str = "valid_time_gmt"
    ) -> pd.Timestamp:
        """Build a pandas Timestamp from a Unix epoch column on a DataFrame row."""
        t = time.localtime(row[column])
        return pd.to_datetime(
            f"{t.tm_year}-{self._two(t.tm_mon)}-{self._two(t.tm_mday)} "
            f"{self._two(t.tm_hour)}:{self._two(t.tm_min)}"
        )

    def _two(self, val: int) -> str:
        """Zero-pad a value to two digits."""
        return str(val).zfill(2)

    def get_loaded_dates(self) -> None:
        """Populate pre_existing_dates with dates already in the DB."""
        sql = f'select distinct dt from talea."{self.table}"'
        out: pd.DataFrame = pd.read_sql(sql=sql, con=self.db.engine)
        self.pre_existing_dates = [v[0] for v in out]

    def pull_date_and_insert(self, dt: str) -> None:
        df = self.pull_historical_weather_underground_data(dt=dt)
        self._insert(df=df)

    # Columns the API returns as object/None that the DB expects as numeric
    _FLOAT_COLS = {
        "precip_total",
        "precip_hrly",
        "gust",
        "max_temp",
        "min_temp",
        "pressure",
        "pressure_tend",
        "wdir",
    }

    def _insert(self, df: pd.DataFrame) -> None:
        for col in self._FLOAT_COLS:
            if col in df.columns and df[col].dtype == object:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df.to_sql(
            name=self.table,
            con=self.db.engine,
            if_exists="append",
            schema="talea",
            index=False,
        )

    @staticmethod
    @functools.cache
    def get_nearest_station(lat: float, lng: float) -> dict:
        """get_nearest_station _summary_

        Args:
            lat (float): _description_
            lng (float): _description_

        Returns:
            dict: _description_
        """
        url = f"https://api.weather.com/v3/location/near?geocode={lat},{lng}&product=observation&format=json&apiKey={API}"
        data = requests.get(url)
        data.raise_for_status()
        return data.json()

    def construct_url_from_lat_lng(
        self, lat: float, lng: float, exclude_station_ids: list
    ) -> str:
        """construct_url_from_lat_lng _summary_

        Args:
            lat (float): _description_
            lng (float): _description_

        Returns:
            str: _description_
        """
        # Assuming 'data' is the JSON response from your v3 call
        # and we want the first (closest) station
        data: dict = HistoricalWeatherData.get_nearest_station(lat=lat, lng=lng)
        loc = data.get("location")
        if not loc:
            raise NotImplementedError

        # Pick the closest station with a standard 4-letter ICAO code
        for i, sid in enumerate(loc["stationId"]):
            if len(sid) == 4 and sid.isalpha() and sid not in exclude_station_ids:
                index = i
                break

        # index = next(
        #     (
        #         i
        #         for i, sid in enumerate(loc["stationId"])

        #     ),
        #     None,
        # )
        if index is None:
            raise ValueError("No ICAO station found near the given coordinates")

        station_id = loc["stationId"][index]
        country = loc["countryCode"][index]
        obs_code = 9

        # Construct the v1 Location ID
        location_id = f"{station_id}:{obs_code}:{country}"

        # Final URL
        historical_url = (
            f"https://api.weather.com/v1/location/{location_id}/observations/historical.json"
            f"?apiKey={API}&units=e&startDate="
        )
        historical_url += "{dt}"
        return historical_url

    def pull_historical_weather_underground_data(
        self,
        dt: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
    ) -> pd.DataFrame:
        """Fetch and store historical Wunderground observations for a YYYYMMDD date string."""
        if dt in self.pre_existing_dates:
            return

        if lat is None:
            url = (
                f"https://api.weather.com/v1/location/KLGA:9:US/observations/historical.json"
                f"?apiKey=e1f10a1e78da46f5b10a1e78da96f525&units=e&startDate={dt}"
            )
            res = requests.get(
                url
                # f"https://api.weather.com/v1/location/KLGA:9:US/observations/historical.json"
                # f"?apiKey=e1f10a1e78da46f5b10a1e78da96f525&units=e&startDate={dt}"
            )
        else:
            exclude_station_ids = []
            flag = True
            i = 0
            while flag:
                url = self.construct_url_from_lat_lng(
                    lat=lat, lng=lng, exclude_station_ids=exclude_station_ids
                ).format(dt=dt)
                res = requests.get(
                    url
                    # f"https://api.weather.com/v1/location/KLGA:9:US/observations/historical.json"
                    # f"?apiKey=e1f10a1e78da46f5b10a1e78da96f525&units=e&startDate={dt}"
                )
                flag = res.status_code != 200
                i += 1
                if i > 20:
                    raise Exception
                # if flag:
                #     x = 1
                exclude_station_ids.append(url.split("/")[5].split(":")[0])
        data = res.json()

        df: pd.DataFrame = pd.DataFrame(data["observations"])
        df["valid_time_gmt_datetime"] = df.apply(
            self.create_datetime_from_column, axis=1
        )
        df["expire_time_gmt_datetime"] = df.apply(
            self.create_datetime_from_column, axis=1, args=("expire_time_gmt",)
        )
        df["expire_time_est_datetime"] = (
            df["expire_time_gmt_datetime"]
            .dt.tz_localize("UTC")
            .dt.tz_convert("US/Eastern")
        ).dt.tz_localize(None)
        df["dt"] = dt
        df["station"] = url.split("/")[5]
        return df

    def backfill(self, start: str, end: str) -> None:
        """Backfill historical data for the hardcoded date range."""
        for ts in sorted(pd.date_range(start=start, end=end), reverse=True):
            dt = str(int(ts.strftime("%Y%m%d")))
            print(dt)
            try:
                df = self.pull_historical_weather_underground_data(dt=dt)
                self._insert(df)
            except Exception as e:
                print(f"Failing {dt}: {e}")
                traceback.print_exc()


if __name__ == "__main__":
    raise SystemExit(
        "Pass a database connection when using HistoricalWeatherData, e.g.:\n"
        "  from talea_db.postgres import db_connect\n"
        "  db = db_connect()\n"
        "  H = HistoricalWeatherData(db=db)"
    )
