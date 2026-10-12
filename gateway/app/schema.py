import strawberry
from strawberry.extensions import MaxAliasesLimiter, QueryDepthLimiter

from app.config import settings


@strawberry.type
class SystemInfo:
    name: str
    version: str
    environment: str
    status: str


@strawberry.type
class Query:
    @strawberry.field
    def system_info(self) -> SystemInfo:
        """Public, non-sensitive gateway metadata; not aggregate service health."""
        return SystemInfo(
            name="Enterprise Task Platform Gateway",
            version="0.1.0",
            environment=settings.app_env,
            status="AVAILABLE",
        )


schema = strawberry.Schema(
    query=Query,
    extensions=[
        lambda: QueryDepthLimiter(max_depth=4),
        lambda: MaxAliasesLimiter(max_alias_count=10),
    ],
)
