import json
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = "http://127.0.0.1:8000"


def get_json(path: str) -> dict:
    with urlopen(f"{BASE_URL}{path}", timeout=10) as response:
        return json.load(response)


def post_json(path: str, payload: dict) -> dict:
    request = Request(
        f"{BASE_URL}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def send_message(session_id: str, message: str) -> dict:
    return post_json(
        "/api/conversation/message",
        {"session_id": session_id, "message": message},
    )


def reset_session(session_id: str) -> dict:
    return post_json(
        "/api/conversation/reset",
        {"session_id": session_id, "message": "__reset__"},
    )


def run_open_ticket_flow(session_id: str) -> dict:
    reset_session(session_id)
    send_message(session_id, "__start__")
    send_message(session_id, "1")
    send_message(session_id, f"wifi caindo no deposito {session_id}")
    send_message(session_id, "1")
    send_message(session_id, "1")
    send_message(session_id, "2")
    send_message(session_id, "TI - Matriz")
    send_message(session_id, "2")
    return send_message(session_id, "1")


def wait_for_runtime_ready(timeout_seconds: int = 90) -> dict:
    deadline = time.time() + timeout_seconds
    last_error = None
    while time.time() < deadline:
        try:
            payload = get_json("/health/runtime")
            if payload.get("redis") == "ok" and payload.get("celery_workers_enabled"):
                return payload
            last_error = payload
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = str(exc)
        time.sleep(2)
    raise RuntimeError(f"Runtime não ficou pronto a tempo: {last_error}")


def main() -> int:
    health = get_json("/health")
    runtime = wait_for_runtime_ready()
    session_prefix = f"smoke-{int(time.time())}"
    single_session = f"{session_prefix}-single"

    created = run_open_ticket_flow(single_session)
    duplicate = send_message(single_session, "1")

    with ThreadPoolExecutor(max_workers=5) as executor:
        multi_results = list(
            executor.map(
                run_open_ticket_flow,
                [f"{session_prefix}-parallel-{index}" for index in range(1, 6)],
            )
        )

    debug_payload = get_json(f"/api/debug/session/{single_session}")

    report = {
        "health": health,
        "runtime": runtime,
        "single_flow_state": created["state"],
        "single_ticket_number": created["created_ticket"]["ticket_number"],
        "post_creation_repeat_message": duplicate["bot_message"],
        "parallel_ticket_numbers": [
            item["created_ticket"]["ticket_number"] for item in multi_results
        ],
        "debug_session_state": debug_payload.get("state"),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
