"""Models API for listing available Perplexity models."""

from __future__ import annotations

from perplexity._core import API_VERSION, PERPLEXITY_BASE_URL, ClientCore
from perplexity.types import Model

_MODELS_CONFIG_URL = f"{PERPLEXITY_BASE_URL}/rest/models/config?config_schema=v1&version={API_VERSION}&source=default"


class ModelsAPI:
    """Interface for querying available models.

    Attributes:
        _core: The underlying HTTP client core.
    """

    def __init__(self, core: ClientCore):
        """Initialize the Models API.

        Args:
            core: ClientCore instance for making HTTP requests.
        """
        self._core = core

    async def list(self, mode: str | None = None) -> list[Model]:
        """Fetch all available models from the Perplexity API.

        Args:
            mode: Optional filter by execution mode (e.g. "search", "research").

        Returns:
            List of Model objects sorted by name.
        """
        data = await self._core.get_json(_MODELS_CONFIG_URL)
        raw_models = data.get("models", {})

        models = [
            Model(
                name=name,
                label=info.get("label", ""),
                description=info.get("description", ""),
                mode=info.get("mode", ""),
                provider=info.get("provider"),
            )
            for name, info in raw_models.items()
        ]

        if mode:
            models = [m for m in models if m.mode == mode]

        return sorted(models, key=lambda m: m.name)
