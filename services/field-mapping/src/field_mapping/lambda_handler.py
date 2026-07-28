"""AWS Lambda entrypoint.

Wraps the FastAPI app with Mangum so the same ASGI app that serves locally under
uvicorn runs unchanged as a container-image Lambda behind a Function URL. Local/
compose runs never import this module, so ``mangum`` is an optional (``[lambda]``)
dependency.
"""

from __future__ import annotations

from mangum import Mangum

from field_mapping.api import create_app

# lifespan="off": Mangum's default runs the ASGI shutdown after each event,
# which closes long-lived clients (httpx) and breaks warm reinvocations —
# Lambda's freeze/thaw model has no meaningful ASGI shutdown point.
handler = Mangum(create_app(), lifespan="off")
