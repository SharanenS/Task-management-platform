"""Custom exception classes mapped to HTTP status codes."""


class AppException(Exception):
    """Base application exception."""

    def __init__(self, detail: str, status_code: int = 500):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class NotFoundError(AppException):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(detail=detail, status_code=404)


class ConflictError(AppException):
    def __init__(self, detail: str = "Resource already exists"):
        super().__init__(detail=detail, status_code=409)


class ForbiddenError(AppException):
    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(detail=detail, status_code=403)


class UnauthorizedError(AppException):
    def __init__(self, detail: str = "Authentication required"):
        super().__init__(detail=detail, status_code=401)


class BadRequestError(AppException):
    def __init__(self, detail: str = "Bad request"):
        super().__init__(detail=detail, status_code=400)