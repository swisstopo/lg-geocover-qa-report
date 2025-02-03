try:
    from ._version import version as __version__
except ImportError:
    import warnings

    warnings.warn(
        "Version information not found. Package is likely not installed correctly."
    )
    __version__ = "0.0.0"

from . import _version
__version__ = _version.get_versions()['version']
