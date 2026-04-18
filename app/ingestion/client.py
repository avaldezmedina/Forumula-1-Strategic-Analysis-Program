from __future__ import annotations
import time
from typing import Any
import httpx
from app.config import settings

class OpenF1ClientError(Exception):
    """Raised when an OpenF1 API request fails or returns invalid data."""


class OpenF1Client:
    """
    HTTP client for the OpenF1 API.

    All methods return raw parsed JSON from the API.
    Transformation and storage happens in ingest.py, not here.
    This class has one job: fetch data reliably.
    """

    def __init__(self) -> None:
        self.base_url = settings.openf1_base_url.rstrip("/")
        self.client = httpx.Client(timeout=30.0)
        self.min_request_interval = 0.5
        self._last_request_time = 0.0

    def _get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Make a rate-limited GET request to the OpenF1 API and return parsed JSON.

        Behavior:
        - Enforces a minimum delay between requests
        - If the API responds with HTTP 429, waits 2 seconds and retries once
        - Raises OpenF1ClientError for transport, HTTP, or JSON failures
        """
        endpoint = endpoint.lstrip("/")
        url = f"{self.base_url}/{endpoint}"

        for attempt in range(2):  # initial try + one retry for 429
            elapsed = time.monotonic() - self._last_request_time
            if elapsed < self.min_request_interval:
                time.sleep(self.min_request_interval - elapsed)

            try:
                response = self.client.get(url, params=params)
                self._last_request_time = time.monotonic()

                if response.status_code == 429 and attempt == 0:
                    time.sleep(2.0)
                    continue

                response.raise_for_status()

            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                raise OpenF1ClientError(
                    f"OpenF1 returned HTTP {status_code} for endpoint='{endpoint}', params={params}"
                ) from exc
            except httpx.RequestError as exc:
                raise OpenF1ClientError(
                    f"OpenF1 request failed for endpoint='{endpoint}', params={params}: {exc}"
                ) from exc

            try:
                data = response.json()
            except ValueError as exc:
                raise OpenF1ClientError(
                    f"OpenF1 returned invalid JSON for endpoint='{endpoint}', params={params}"
                ) from exc

            if not isinstance(data, list):
                raise OpenF1ClientError(
                    f"Expected list response from OpenF1 for endpoint='{endpoint}', "
                    f"got {type(data).__name__}"
                )

            return data

        raise OpenF1ClientError(
            f"OpenF1 returned HTTP 429 twice for endpoint='{endpoint}', params={params}"
        )

    def get_meetings(self, year: int) -> list[dict[str, Any]]:
        """Fetch all meetings (race weekends) for a given year."""
        return self._get("meetings", params={"year": year})

    def get_meeting(self, meeting_key: int) -> dict[str, Any]:
        """Fetch a single meeting by meeting_key."""
        rows = self._get("meetings", params={"meeting_key": meeting_key})

        if not rows:
            raise OpenF1ClientError(f"No meeting found for meeting_key={meeting_key}")

        if len(rows) > 1:
            raise OpenF1ClientError(
                f"Expected one meeting for meeting_key={meeting_key}, got {len(rows)}"
            )

        return rows[0]

    def get_sessions(self, meeting_key: int) -> list[dict[str, Any]]:
        """
        Fetch all sessions for a given meeting.

        Fetch all here and filter in ingest.py so the client remains a thin
        wrapper around the raw API.
        """
        return self._get("sessions", params={"meeting_key": meeting_key})

    def get_session(self, session_key: int) -> dict[str, Any]:
        """Fetch a single session by session_key."""
        rows = self._get("sessions", params={"session_key": session_key})

        if not rows:
            raise OpenF1ClientError(f"No session found for session_key={session_key}")

        if len(rows) > 1:
            raise OpenF1ClientError(
                f"Expected one session for session_key={session_key}, got {len(rows)}"
            )

        return rows[0]

    def get_laps(self, session_key: int, driver_number: int) -> list[dict[str, Any]]:
        """Fetch all laps for a driver in a session."""
        return self._get(
            "laps",
            params={
                "session_key": session_key,
                "driver_number": driver_number,
            },
        )

    def get_stints(self, session_key: int) -> list[dict[str, Any]]:
        """Fetch all stints for a session."""
        return self._get("stints", params={"session_key": session_key})

    def get_pit_stops(self, session_key: int) -> list[dict[str, Any]]:
        """Fetch all pit lane events for a session."""
        return self._get("pit", params={"session_key": session_key})

    def get_race_control(self, session_key: int) -> list[dict[str, Any]]:
        """Fetch all race control messages for a session."""
        return self._get("race_control", params={"session_key": session_key})

    def get_drivers(self, session_key: int) -> list[dict[str, Any]]:
        """Fetch all drivers for a session."""
        return self._get("drivers", params={"session_key": session_key})

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self.client.close()
