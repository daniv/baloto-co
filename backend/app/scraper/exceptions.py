"""Exceptions raised while registering validators or loading lottery result pages."""


class DuplicateValidatorError(ValueError):
    """
    Report one or more duplicate validator names.

    The exception is raised before registry mutation so failed registration
    operations remain atomic.
    """

    def __init__(self, validator_names: tuple[str, ...]) -> None:
        """
        Initialize an error for duplicated validator names.

        :param validator_names: Sorted or discovered validator names that conflict.
        """
        self.validator_names = validator_names
        formatted_names = ", ".join(repr(name) for name in validator_names)
        error_message = f"Validator names must be unique. Duplicates found: {formatted_names}."
        super().__init__(error_message)


class ValidatorNotRegisteredError(LookupError):
    """
    Report an attempt to remove an unknown validator.

    The missing validator name is retained on the exception for programmatic
    inspection by callers and tests.
    """

    def __init__(self, validator_name: str) -> None:
        """
        Initialize an error for an unregistered validator.

        :param validator_name: Name requested from the registry.
        """
        self.validator_name = validator_name
        error_message = f"Validator {validator_name!r} is not registered."
        super().__init__(error_message)


class DrawPageNotFoundError(ValueError):
    """Indicate that the website did not return the requested draw page."""
