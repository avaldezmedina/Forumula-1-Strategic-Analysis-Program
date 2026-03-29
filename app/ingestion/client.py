import httpx
from typing import Any
from app.config import settings


class OpenF1Client:
    """
    HTTP client for the OpenF1 API.
    All methods return raw parsed JSON from the API.
    Transformation and storage happens in ingest.py, not here.
    This class has one job: fetch data reliably.
    """

    def __init__(self):
        self.base_url = settings.openf1_base_url
        # TODO: understand what timeout means here and why it matters
        self.client = httpx.Client(timeout=30.0)

    def _get(self, endpoint: str, params: dict) -> list[dict[str, Any]]:
        """
        Make a GET request to the OpenF1 API.

        TODO: Implement this method. It should:
        1. Build the full URL from self.base_url and endpoint
        2. Make the request with the provided params
        3. Raise an exception if the response status is not 200
        4. Return the parsed JSON response

        Think about: what happens if the API is down? What if it returns
        a non-JSON response? Handle these cases explicitly.
        """
        raise NotImplementedError

    def get_meetings(self, year: int) -> list[dict[str, Any]]:
        """
        Fetch all meetings (race weekends) for a given year.

        TODO: implement using self._get()
        Hint: check the OpenF1 docs for the correct endpoint and params.
        """
        raise NotImplementedError

    def get_sessions(self, meeting_key: int) -> list[dict[str, Any]]:
        """
        Fetch all sessions for a given meeting.

        TODO: implement using self._get()
        You only want Race sessions ultimately, but fetch all here
        and filter in ingest.py. Why is that a better design?
        """
        raise NotImplementedError

    def get_laps(self, session_key: int, driver_number: int) -> list[dict[str, Any]]:
        """
        Fetch all laps for a driver in a session.

        TODO: implement using self._get()
        """
        raise NotImplementedError

    def get_stints(self, session_key: int) -> list[dict[str, Any]]:
        """
        Fetch all stints for a session.

        TODO: implement using self._get()
        """
        raise NotImplementedError

    def get_pit_stops(self, session_key: int) -> list[dict[str, Any]]:
        """
        Fetch all pit stops for a session.

        TODO: implement using self._get()
        """
        raise NotImplementedError

    def get_race_control(self, session_key: int) -> list[dict[str, Any]]:
        """
        Fetch all race control messages for a session.

        TODO: implement using self._get()
        """
        raise NotImplementedError

    def get_drivers(self, session_key: int) -> list[dict[str, Any]]:
        """
        Fetch all drivers for a session.

        TODO: implement using self._get()
        """
        raise NotImplementedError
