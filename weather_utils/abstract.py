import abc
import datetime
import typing

import httpx
import pydantic


class HarmonizedWeather(pydantic.BaseModel):
    timestamp: datetime.datetime
    temp_max: float
    temp_min: float
    is_raining: bool = False
    is_snowing: bool = False
    window_has_precip: typing.Optional[bool] = None
    source_api: str


class WeatherProvider(abc.ABC):
    def __init__(self, user_agent: str = "MyWeatherApp/1.0"):
        self.client = httpx.Client(headers={"User-Agent": user_agent})

    @abc.abstractmethod
    def get_daily_data(
        self, lat: float, lon: float, date: datetime.date
    ) -> HarmonizedWeather:
        """Fetch and harmonize weather data for a specific date/location."""
        pass

    def _convert_c_to_f(self, celsius: float) -> float:
        return (celsius * 9 / 5) + 32
