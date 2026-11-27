from typing import Dict, List, Optional, Tuple
from importlib import import_module
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
        """Resolve a provider integration by name and product.

        Provider modules register their singleton as an import side effect.  The
        API imports those modules through its routers, but Celery starts from a
        task module and therefore does not necessarily import any API router.
        Load the built-in provider on demand so resolution is independent of
        process entrypoint and import order.
        """
        name = provider_name.lower().strip()
        product_name = product.lower().strip()
        provider = self._providers.get((name, product_name))
        if provider is None:
            builtins = {
                ("zoho", "crm"): ("app.integrations.zoho.integration", "zoho_integration"),
                ("zoho", "books"): ("app.integrations.zoho.books_integration", "zoho_books_integration"),
                ("odoo", "erp"): ("app.integrations.odoo.integration", "odoo_integration"),
                ("business_central", "erp"): ("app.integrations.business_central.integration", "business_central_integration"),
            }
            provider_spec = builtins.get((name, product_name))
            if provider_spec:
                module_name, provider_name = provider_spec
                provider = getattr(import_module(module_name), provider_name)
                self.register(provider)
                provider = self._providers.get((name, product_name))
        return provider

    def list_providers(self) -> List[str]:
        """List all currently registered ERP provider names."""
        return [f"{provider}:{product}" for provider, product in self._providers.keys()]


# Singleton instance of the integration registry
integration_registry = IntegrationRegistry()

