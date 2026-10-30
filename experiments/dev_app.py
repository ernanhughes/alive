"""Development helper: run the API with the opt-in research harness."""

from alive.app import create_app


def create_experiment_app(settings=None):
    """Create the full app with ``alive/experiment`` routes and runner enabled."""
    return create_app(settings, include_experiments=True)
