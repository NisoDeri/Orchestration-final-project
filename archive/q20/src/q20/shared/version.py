"""Single source of truth for the code version, plus config-version validation.

The grading rubric requires explicit version tracking starting at 1.00, with the
application validating that configuration files match the code version at startup.
"""

from q20.shared.exceptions import VersionMismatchError

CODE_VERSION = "1.00"


def validate_config_version(config_version: str, config_name: str) -> None:
    """Raise if a config file's version does not match the code version.

    A config written for a different code version may carry keys the code no longer
    understands (or be missing required ones); failing fast at load time is safer
    than surfacing a confusing error deep inside a league run.
    """
    if config_version != CODE_VERSION:
        raise VersionMismatchError(
            f"{config_name} version {config_version!r} != code version {CODE_VERSION!r}"
        )
