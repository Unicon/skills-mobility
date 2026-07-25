"""AWS Lambda entrypoint.

Wraps the FastAPI app with Mangum so the same ASGI app that serves locally under
uvicorn runs unchanged as a container-image Lambda behind a Function URL. Local/
compose runs never import this module, so ``mangum`` is an optional (``[lambda]``)
dependency.
"""

from __future__ import annotations

from mangum import Mangum

from field_synthesis.api import create_app

handler = Mangum(create_app())
