"""datamole - Simple data versioning for ML projects."""

try:
    from datamole._version import version as __version__
except ImportError:
    __version__ = "0.1.0.dev0"

from datamole.core import DataMole

__all__ = ["DataMole", "__version__"]
