from typing import Dict, List, Optional
from app.integrations.base import BaseERPIntegration


class IntegrationRegistry:
    """
    Registry for ERP integration modules.
    Enables dynamic registration and resolution of provider implementations (Zoho, Odoo, SAP).
    """

    def __init__(self) -> None:
        self._providers: Dict[str, BaseERPIntegration] = {}

    def register(self, provider: BaseERPIntegration) -> None:
        """Register a provider integration implementation."""
        name = provider.provider_name.lower().strip()
        self._providers[name] = provider

    def get(self, provider_name: str) -> Optional[BaseERPIntegration]:
        """Resolve a provider integration by name."""
        name = provider_name.lower().strip()
        provider = self._providers.get(name)
        if provider is None and name == "zoho":
            # Workers can import this registry without importing the API router.
            # Load built-ins lazily so registration does not depend on import order.
            from app.integrations.zoho.integration import zoho_integration

            self.register(zoho_integration)
            provider = self._providers.get(name)
        return provider

    def list_providers(self) -> List[str]:
        """List all currently registered ERP provider names."""
        return list(self._providers.keys())


# Singleton instance of the integration registry
integration_registry = IntegrationRegistry()

