"""Gunicorn / local WSGI entrypoint."""
from ema import create_app
app = create_app()