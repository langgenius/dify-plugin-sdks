from typing import Optional


class EndpointSetupFailedError(Exception):
    """
    The error that occurs when the endpoint setup failed
    """

    description: Optional[str] = None

    def __init__(self, description: Optional[str] = None) -> None:
        if description:
            self.description = description

    def __str__(self):
        return self.description or self.__class__.__name__
