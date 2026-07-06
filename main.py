import json
import uuid
import time
from collections import defaultdict, deque
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Scope, Receive, Send

app = FastAPI(title="FastAPI Middleware Assignment Service")

# 1. Rate Limiting State and Middleware
RATE_LIMIT = 9
WINDOW_SECONDS = 10.0
client_buckets = defaultdict(deque)

class RateLimitASGIMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # OPTIONS preflight requests should not be rate-limited
        if scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return

        # Extract X-Client-Id header (lower-cased in ASGI scope headers)
        headers = dict(scope.get("headers", []))
        client_id_bytes = headers.get(b"x-client-id")
        client_id = client_id_bytes.decode("utf-8") if client_id_bytes else "anonymous"

        current_time = time.time()
        bucket = client_buckets[client_id]

        # Clean up expired timestamps continuously
        while bucket and bucket[0] < current_time - WINDOW_SECONDS:
            bucket.popleft()

        if len(bucket) >= RATE_LIMIT:
            # Return HTTP 429 response immediately
            response_body = json.dumps({"error": "Rate limit exceeded"}).encode("utf-8")
            await send({
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(response_body)).encode("utf-8")),
                ]
            })
            await send({
                "type": "http.response.body",
                "body": response_body,
                "more_body": False
            })
            return

        bucket.append(current_time)
        await self.app(scope, receive, send)


# 2. Request Context ASGI Middleware
class RequestContextASGIMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract or generate X-Request-ID
        headers = dict(scope.get("headers", []))
        request_id_bytes = headers.get(b"x-request-id")
        if request_id_bytes:
            request_id = request_id_bytes.decode("utf-8")
        else:
            request_id = str(uuid.uuid4())

        # Store in ASGI scope state so request.state.request_id is populated
        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["request_id"] = request_id

        # Response modification variables
        response_body = b""
        response_status = 200
        response_headers = []

        async def send_wrapper(message: dict) -> None:
            nonlocal response_body, response_status, response_headers

            if message["type"] == "http.response.start":
                response_status = message["status"]
                response_headers = message["headers"]

            elif message["type"] == "http.response.body":
                response_body += message.get("body", b"")
                
                # If there's no more body, process and send the response
                if not message.get("more_body", False):
                    # Check if response is successful JSON response
                    is_json = False
                    content_length_idx = -1
                    for idx, (k, v) in enumerate(response_headers):
                        if k.lower() == b"content-type" and b"application/json" in v:
                            is_json = True
                        if k.lower() == b"content-length":
                            content_length_idx = idx

                    if is_json and response_status == 200:
                        try:
                            data = json.loads(response_body.decode("utf-8"))
                            if isinstance(data, dict):
                                # If request_id exists in dict, or if path is /ping, override it
                                if "request_id" in data or scope.get("path") == "/ping":
                                    data["request_id"] = request_id
                                    response_body = json.dumps(data).encode("utf-8")
                                    # Update content-length header
                                    new_len = str(len(response_body)).encode("utf-8")
                                    if content_length_idx != -1:
                                        response_headers[content_length_idx] = (b"content-length", new_len)
                                    else:
                                        response_headers.append((b"content-length", new_len))
                        except Exception:
                            pass

                    # Ensure X-Request-ID is present in the response headers (overwrite if already set)
                    response_headers = [h for h in response_headers if h[0].lower() != b"x-request-id"]
                    response_headers.append((b"x-request-id", request_id.encode("utf-8")))

                    # Emit the start and body messages to client
                    await send({
                        "type": "http.response.start",
                        "status": response_status,
                        "headers": response_headers
                    })
                    await send({
                        "type": "http.response.body",
                        "body": response_body,
                        "more_body": False
                    })
                    return

            # Pass other messages through
            if message["type"] not in ("http.response.start", "http.response.body"):
                await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            raise e


# Add Middlewares in correct execution order
# Request flow: Client -> CORS -> Request Context -> Rate Limiter -> FastAPI Router
# Since app.add_middleware wraps the application, the last added middleware runs first.
app.add_middleware(RateLimitASGIMiddleware)
app.add_middleware(RequestContextASGIMiddleware)

# Configured Scoped CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app-g8swuy.example.com",
        "https://exam.sanand.workers.dev"
    ],
    allow_origin_regex=r"https://([a-zA-Z0-9-]+\.)*iitm\.ac\.in",
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/ping")
async def ping(request: Request) -> dict:
    return {
        "email": "23f1002228@ds.study.iitm.ac.in",
        "request_id": request.state.request_id
    }
