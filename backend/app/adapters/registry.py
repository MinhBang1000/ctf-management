from app.adapters.base import AdapterError, PlatformAdapter
from app.adapters.rootme import RootMeAdapter
from app.models.platform import Platform

# New adapters (PRD §4.3 — TryHackMe etc.) register here. Anything not in
# this map is rejected on Platform creation rather than silently accepted.
ADAPTER_REGISTRY: dict[str, type[PlatformAdapter]] = {
    "rootme": RootMeAdapter,
}


def get_adapter(platform: Platform) -> PlatformAdapter:
    adapter_cls = ADAPTER_REGISTRY.get(platform.adapter_type)
    if not adapter_cls:
        raise AdapterError(f"No adapter implemented for adapter_type={platform.adapter_type!r}")
    config = dict(platform.auth_config or {})
    return adapter_cls(base_url=platform.base_url, **config)
