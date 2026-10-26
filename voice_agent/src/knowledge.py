"""Authoritative local-clock timezone conversion for UATU."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from livekit.agents import RunContext, function_tool
from livekit.agents.llm import ToolError


def current_time(location: str = "Asia/Kolkata", *, now: datetime | None = None) -> dict:
    aliases = {
        "india": "Asia/Kolkata",
        "ist": "Asia/Kolkata",
        "chennai": "Asia/Kolkata",
        "delhi": "Asia/Kolkata",
        "mumbai": "Asia/Kolkata",
        "kolkata": "Asia/Kolkata",
        "utc": "UTC",
        "london": "Europe/London",
        "new york": "America/New_York",
    }
    name = aliases.get(location.strip().casefold(), location.strip())
    try:
        zone = ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(
            "Unknown timezone. Use Asia/Kolkata, India, or an IANA timezone such as Europe/London."
        ) from exc
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("The reference instant must include a timezone.")
    local = instant.astimezone(zone)
    return {
        "timezone": name,
        "date": local.date().isoformat(),
        "time_24h": local.strftime("%H:%M:%S"),
        "time_12h": local.strftime("%I:%M:%S %p"),
        "utc_offset": local.strftime("%z"),
        "source": "Computer system clock, converted using timezone data; not model memory.",
    }


class KnowledgeTools:
    """Tools for authoritative time and system clock queries."""

    def __init__(self):
        pass

    @property
    def tools(self):
        return [self.get_current_time]

    @function_tool()
    async def get_current_time(
        self, context: RunContext, location: str = "Asia/Kolkata"
    ) -> dict:
        """Get the actual current date/time from the system clock in a timezone.

        Always use for current-time questions. Default is Asia/Kolkata (IST UTC+5:30).
        Other places should use IANA timezone names. Never guess the current time.
        """
        try:
            return current_time(location)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
