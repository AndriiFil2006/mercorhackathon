"""Sanitized errors only; never expose raw provider exception messages."""
class GenerationError(Exception):
    def __init__(self, category: str, message: str, http_status: int = 502):
        super().__init__(message)
        self.category = category
        self.message = message
        self.http_status = http_status

