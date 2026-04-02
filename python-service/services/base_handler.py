"""Abstract base class for all service handlers."""

from abc import ABC, abstractmethod
from typing import Any


class ServiceHandler(ABC):
    """Base class for Sinric Pro service handlers.

    Each concrete handler manages one logical device (e.g., a WiFi SSID,
    a garage door, a smart light) and translates Sinric Pro actions into
    the appropriate downstream API calls.
    """

    def __init__(self, device_id: str, service_type: str, config: dict) -> None:
        self.device_id = device_id
        self.service_type = service_type
        self.config = config

    @abstractmethod
    async def handle_action(self, action: str, value: dict) -> dict:
        """Handle a Sinric Pro action request.

        Returns:
            dict with keys: success (bool), message (str), value (dict)
        """

    @abstractmethod
    async def get_state(self) -> Any:
        """Return the current state of the device."""

    async def get_details(self) -> dict:
        """Return full device details. Override for richer info."""
        return {"state": await self.get_state()}

    async def verify_configuration(self) -> bool:
        """Optional pre-flight validation. Override to add checks."""
        return True

    async def cleanup(self) -> None:
        """Optional cleanup on shutdown."""
