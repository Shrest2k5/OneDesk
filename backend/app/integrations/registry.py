from typing import Dict, List, Optional, Tuple
from app.integrations.base import BaseERPIntegration


class IntegrationRegistry:
    """
    Registry for ERP integration modules.
    Enables dynamic registration and resolution of provider implementations (Zoho, Odoo, SAP).
    """

    def __init__(self) -> None:
        self._providers: Dict[Tuple[str, str], BaseERPIntegration] = {}

    def register(self, provider: BaseERPIntegration) -> None:
        """Register a provider integration implementation."""
        name = provider.provider_name.lower().strip()
        product = getattr(provider, "product_name", "crm").lower().strip()
        self._providers[(name, product)] = provider

    def get(self, provider_name: str, product: str = "crm") -> Optional[BaseERPIntegration]:
        """Resolve a provider integration by name."""
        name = provider_name.lower().strip()
        provider = self._providers.get((name, product.lower().strip()))
        if provider is None and name == "zoho" and product == "crm":
            # Workers can import this registry without importing the API router.
            # Load built-ins lazily so registration does not depend on import order.
            from app.integrations.zoho.integration import zoho_integration

            self.register(zoho_integration)
            provider = self._providers.get((name, "crm"))
        return provider

    def list_providers(self) -> List[str]:
        """List all currently registered ERP provider names."""
        return [f"{provider}:{product}" for provider, product in self._providers.keys()]


# Singleton instance of the integration registry
integration_registry = IntegrationRegistry()

