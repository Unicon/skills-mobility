"""AWS Lambda entrypoint.

Wraps the FastAPI app with Mangum so the same ASGI app that serves locally under
uvicorn runs unchanged as a container-image Lambda behind a Function URL (the
synchronous HTTP demo topology; no async event model). Local/compose runs never
import this module, so ``mangum`` is an optional (``[lambda]``) dependency.
"""

from __future__ import annotations

from mangum import Mangum

from event_consumer.app import create_app

# lifespan="off": Mangum's default runs the ASGI shutdown after each event,
# which closes long-lived clients (httpx) and breaks warm reinvocations —
# Lambda's freeze/thaw model has no meaningful ASGI shutdown point.
handler = Mangum(create_app(), lifespan="off")
