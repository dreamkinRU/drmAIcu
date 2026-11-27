"""Loopback production frontend: static snapshot plus streaming API proxy."""
import os
import shutil
import tempfile
from pathlib import Path

import requests
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

ROOT = Path(__file__).resolve().parent
HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
       "te", "trailer", "transfer-encoding", "upgrade", "host", "content-length"}


def create_app(directory):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
    async def proxy(path: str, request: Request):
        # Fixed loopback upstream; never forward arbitrary URLs or follow redirects.
        raw_path = request.scope.get("raw_path", b"").decode("ascii")
        url = "http://127.0.0.1:8080" + raw_path
        if request.url.query:
            url += "?" + request.url.query
        headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP}
        headers["Accept-Encoding"] = "identity"
        body = await request.body()
        def send():
            session = requests.Session()
            session.trust_env = False
            try:
                response = session.request(request.method, url, headers=headers, data=body,
                                           stream=True, timeout=(5, 3600), allow_redirects=False)
            except Exception:
                session.close()
                raise
            return session, response
        try:
            session, response = await run_in_threadpool(send)
        except requests.RequestException:
            return Response('{"success":false,"error":"Core unavailable"}', status_code=503, media_type="application/json")
        def chunks():
            try:
                yield from response.raw.stream(8192, decode_content=False)
            finally:
                response.close()
                session.close()
        return StreamingResponse(chunks(), status_code=response.status_code,
                                 headers={k: v for k, v in response.headers.items() if k.lower() not in HOP})

    app.mount("/", StaticFiles(directory=str(directory), html=True), name="frontend")
    return app


if __name__ == "__main__":
    import uvicorn
    # An immutable per-process snapshot keeps the active UI available during rebuild.
    with tempfile.TemporaryDirectory(prefix="drmaicu-ui-") as temp:
        shutil.copytree(ROOT / "dist", Path(temp) / "dist")
        uvicorn.run(create_app(Path(temp) / "dist"), host="127.0.0.1", port=5173)
