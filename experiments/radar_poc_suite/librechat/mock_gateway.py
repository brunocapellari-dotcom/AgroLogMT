from __future__ import annotations

import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
PORT = 8765
MODEL_ID = "agrolog-mock"


class Handler(BaseHTTPRequestHandler):
    server_version = "AgroLogMockGateway/0.1"

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        print("[mock_gateway] " + fmt % args)

    def do_GET(self) -> None:
        if self.path == "/v1/models":
            self._json(
                200,
                {
                    "object": "list",
                    "data": [
                        {
                            "id": MODEL_ID,
                            "object": "model",
                            "owned_by": "agrolog-poc",
                        }
                    ],
                },
            )
            return
        if self.path == "/healthz":
            self._json(200, {"status": "ok", "bigquery_access": False})
            return
        self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        if self.path != "/v1/chat/completions":
            self._json(404, {"error": "not_found"})
            return

        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 1_000_000:
                raise ValueError("invalid content length")
            payload = json.loads(self.rfile.read(size).decode("utf-8"))
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._json(400, {"error": f"invalid_request: {exc}"})
            return

        messages = payload.get("messages") or []
        last_user = ""
        for message in reversed(messages):
            if isinstance(message, dict) and message.get("role") == "user":
                last_user = str(message.get("content", ""))
                break

        reply = (
            "PoC AgroLog: recebi a pergunta via boundary compatível com OpenAI. "
            "Este mock não consulta BigQuery, não usa credenciais e não representa resposta analítica real. "
            f"Pergunta recebida: {last_user[:500]}"
        )
        now = int(time.time())
        self._json(
            200,
            {
                "id": f"chatcmpl-agrolog-{now}",
                "object": "chat.completion",
                "created": now,
                "model": MODEL_ID,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": reply},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            },
        )


def main() -> None:
    print(f"AgroLog mock Gateway em http://{HOST}:{PORT}/v1")
    print("Bound to localhost only. BigQuery access: disabled.")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
