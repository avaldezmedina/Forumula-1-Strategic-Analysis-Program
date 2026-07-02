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

    # Delays (seconds) to wait after a 429 before each retry attempt.
    # 5s, 15s, 30s, 60s — chosen to give the OpenF1 API time to recover.
    _RETRY_DELAYS = [5, 15, 30, 60]

    def __init__(self) -> None:
        self.base_url = settings.openf1_base_url.rstrip("/")
        self.client = httpx.Client(timeout=30.0)
        # Minimum gap between any two requests to stay under OpenF1 rate limits.
        self.min_request_interval = 1.0
        self._last_request_time = 0.0

    def _get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Make a rate-limited GET request to the OpenF1 API and return parsed JSON.

        Behavior:
        - Enforces a minimum gap between requests (min_request_interval)
        - On HTTP 429, backs off exponentially up to len(_RETRY_DELAYS) times
        - Raises OpenF1ClientError for transport, HTTP, or JSON failures
        """
        endpoint = endpoint.lstrip("/")
        url = f"{self.base_url}/{endpoint}"

        max_attempts = 1 + len(self._RETRY_DELAYS)  # initial + retries

        for attempt in range(max_attempts):
            elapsed = time.monotonic() - self._last_request_time
            if elapsed < self.min_request_interval:
                time.sleep(self.min_request_interval - elapsed)

            try:
                response = self.client.get(url, params=params)
                self._last_request_time = time.monotonic()
            except httpx.RequestError as exc:
                raise OpenF1ClientError(
                    f"OpenF1 request failed for endpoint='{endpoint}', params={params}: {exc}"
                ) from exc

            if response.status_code == 429:
                if attempt < len(self._RETRY_DELAYS):
                    delay = self._RETRY_DELAYS[attempt]
                    time.sleep(delay)
                    continue
                raise OpenF1ClientError(
                    f"OpenF1 returned HTTP 429 after {attempt + 1} attempts "
                    f"for endpoint='{endpoint}', params={params}"
                )

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise OpenF1ClientError(
                    f"OpenF1 returned HTTP {exc.response.status_code} "
                    f"for endpoint='{endpoint}', params={params}"
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
            f"OpenF1 returned HTTP 429 after all retries for endpoint='{endpoint}', params={params}"
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

    def get_location(
        self,
        session_key: int,
        driver_number: int | None = None,
        date_gt: str | None = None,
        date_lt: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch car location samples for a session.

        If driver_number is None, returns samples for all drivers (useful for
        bulk fetching to minimise API calls).
        """
        params: dict[str, Any] = {"session_key": session_key}
        if driver_number is not None:
            params["driver_number"] = driver_number
        if date_gt is not None:
            params["date>"] = date_gt
        if date_lt is not None:
            params["date<"] = date_lt
        return self._get("location", params=params)

    def get_position(
        self,
        session_key: int,
        driver_number: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch position changes for a session, optionally filtered by driver."""
        params: dict[str, Any] = {"session_key": session_key}
        if driver_number is not None:
            params["driver_number"] = driver_number
        return self._get("position", params=params)

    def get_intervals(
        self,
        session_key: int,
        driver_number: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch interval/gap data for a session, optionally filtered by driver."""
        params: dict[str, Any] = {"session_key": session_key}
        if driver_number is not None:
            params["driver_number"] = driver_number
        return self._get("intervals", params=params)

    def get_location_windowed(
        self,
        session_key: int,
        driver_number: int,
        date_gt: str,
        date_lt: str,
        window_seconds: int = 300,
    ) -> list[dict[str, Any]]:
        """
        Fetch location samples for one driver within a time range, split into
        windows to avoid oversized responses.
        """
        return self._get_location_windowed_impl(
            session_key=session_key,
            driver_number=driver_number,
            date_gt=date_gt,
            date_lt=date_lt,
            window_seconds=window_seconds,
        )

    def get_location_all_drivers_windowed(
        self,
        session_key: int,
        date_gt: str,
        date_lt: str,
        window_seconds: int = 300,
    ) -> dict[int, list[dict[str, Any]]]:
        """
        Fetch location samples for ALL drivers in a session within a time range,
        using one API call per time window (no per-driver filtering).

        Returns a dict mapping driver_number -> list of location samples sorted
        by timestamp.  This collapses N_drivers × N_windows calls into just
        N_windows calls, dramatically reducing the risk of 429 rate limiting.
        """
        raw = self._get_location_windowed_impl(
            session_key=session_key,
            driver_number=None,
            date_gt=date_gt,
            date_lt=date_lt,
            window_seconds=window_seconds,
        )

        by_driver: dict[int, list[dict[str, Any]]] = {}
        for row in raw:
            dn = row.get("driver_number")
            if dn is None:
                continue
            by_driver.setdefault(int(dn), []).append(row)

        for samples in by_driver.values():
            samples.sort(key=lambda r: r.get("date", ""))

        return by_driver

    def _get_location_windowed_impl(
        self,
        session_key: int,
        driver_number: int | None,
        date_gt: str,
        date_lt: str,
        window_seconds: int = 300,
    ) -> list[dict[str, Any]]:
        from datetime import datetime, timedelta, timezone

        def _parse(ts: str) -> datetime:
            normalized = ts.replace("Z", "+00:00")
            dt = datetime.fromisoformat(normalized)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt

        def _fmt(dt: datetime) -> str:
            return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        start = _parse(date_gt)
        end = _parse(date_lt)
        window = timedelta(seconds=window_seconds)

        samples: list[dict[str, Any]] = []
        cursor = start

        while cursor < end:
            chunk_end = min(cursor + window, end)
            try:
                chunk = self.get_location(
                    session_key=session_key,
                    driver_number=driver_number,  # type: ignore[arg-type]
                    date_gt=_fmt(cursor),
                    date_lt=_fmt(chunk_end),
                )
            except OpenF1ClientError as exc:
                # OpenF1 returns 404 when a time window has no location data
                # (e.g. past the end of the session). Treat as end-of-data and
                # stop fetching further windows — subsequent ones will also 404.
                if "HTTP 404" in str(exc):
                    break
                raise
            samples.extend(chunk)
            cursor = chunk_end

        samples.sort(key=lambda row: row.get("date", ""))
        return samples

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self.client.close()
