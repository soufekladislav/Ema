"""cPanel / Phusion Passenger WSGI entrypoint."""
from ema import create_app
application = create_app()