"""Locate checkout-local configs/data separately from packaged map resources."""
import os
from pathlib import Path


def project_root():
    override = os.environ.get('FEC_PROJECT_DIR')
    if override:
        return Path(override).expanduser().resolve()
    checkout = Path(__file__).resolve().parents[2]
    if (checkout / 'pyproject.toml').is_file():
        return checkout
    # A wheel contains reusable code/map assets, not local configs or migrations.
    return Path.cwd().resolve()


PROJECT_ROOT = project_root()
