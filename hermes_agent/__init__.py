"""The Hermes Agent package — CT101 native integration.

Import this package to access the full CT101 stack directly:
    from hermes_agent.ct101 import domain, infra, cpp, bots, overview

Also available as a top-level convenience:
    from hermes_agent import ct101
"""

# Lazy-load CT101 on first access to avoid slowing down Hermes startup.
# The C++ bridge initializes on first use, connecting to PostgreSQL and
# loading libtradeengine_core.so.

_ct101_cache = None


def __getattr__(name: str):
    global _ct101_cache
    if name == "ct101":
        if _ct101_cache is None:
            from hermes_agent.ct101 import domain, infra, cpp, bots, overview  # noqa: F811
            import hermes_agent.ct101 as _mod
            _ct101_cache = _mod
        return _ct101_cache
    raise AttributeError(f"module 'hermes_agent' has no attribute {name!r}")