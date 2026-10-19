import os
from functools import cache

from dotenv import load_dotenv
from phoenix.otel import register


@cache
def configure_tracing() -> None:
    load_dotenv()
    register(
        project_name=os.getenv("PHOENIX_PROJECT_NAME", "assay"),
        protocol="http/protobuf",
        batch=True,
        verbose=False,
        auto_instrument=True,
    )
