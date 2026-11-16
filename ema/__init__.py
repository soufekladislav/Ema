"""EMA / Fresh HUB."""

def create_app(*args, **kwargs):
    from .web import create_app as factory
    return factory(*args, **kwargs)

__all__ = ["create_app"]