import sys
from datetime import datetime

from portable_common import STATE_DIR, atomic_write_json, read_json


def main():
    state_path = STATE_DIR / "collector_state.json"
    output_path = STATE_DIR / "new_messages.json"
    state = read_json(state_path, {"initialized": True, "sessions": {}, "pending": []})
    state["pending"] = []
    state["acknowledgedAt"] = datetime.now().astimezone().isoformat()
    atomic_write_json(state_path, state)
    atomic_write_json(output_path, {
        "ok": True,
        "data": {"messages": []},
        "meta": {"total": 0, "acknowledged": True},
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
