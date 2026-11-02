class NgError(Exception):
    """An actionable API error that never includes credentials or raw DB errors."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code
