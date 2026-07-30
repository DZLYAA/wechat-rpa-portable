import hashlib
import json
import sys
from datetime import datetime

from portable_common import (
    LOG_DIR,
    STATE_DIR,
    atomic_write_json,
    call_ciphertalk,
    ensure_ciphertalk_ready,
    load_config,
    log_status,
    read_json,
)


STATE_PATH = STATE_DIR / "collector_state.json"
OUTPUT_PATH = STATE_DIR / "new_messages.json"


def message_key(session_id, message):
    message_id = str(message.get("messageId") or "")
    if message_id and message_id != "0":
        return f"{session_id}|M|{message_id}"
    cursor = message.get("cursor") or {}
    return (
        f"{session_id}|L|{cursor.get('localId', '')}|"
        f"{message.get('timestamp', '')}|{message.get('direction', '')}"
    )


def preview_key(session_id, session):
    preview = str(session.get("lastMessagePreview") or "")
    digest = hashlib.sha256(preview.encode("utf-8")).hexdigest()[:16]
    return f"{session_id}|P|{session.get('lastTimestamp', '')}|{digest}"


def excel_safe(value):
    text = str(value or "")[:32767]
    return "'" + text if text.startswith(("=", "+", "-", "@")) else text


def local_time(value):
    try:
        raw = float(value)
        timestamp = raw / 1000 if raw > 1e12 else raw
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def sender_label(sender, session):
    sender = sender or {}
    username = str(sender.get("username") or "").strip()
    display = str(sender.get("displayName") or "").strip()
    fallback = (
        str(session.get("displayName") or "").strip()
        if session.get("kind") != "group"
        else ""
    )
    if sender.get("isSelf"):
        return f"我（{username}）" if username else "我"
    if display and username and display != username and not display.lower().startswith(
        ("wxid_", "gh_")
    ):
        return f"{display}（{username}）"
    if fallback and username:
        return f"{fallback}（{username}）"
    return fallback or display or username


def get_messages(session_id, limit, config):
    return call_ciphertalk(
        "get_messages",
        {
            "sessionId": session_id,
            "offset": 0,
            "limit": limit,
            "order": "desc",
            "includeRaw": False,
            "includeMediaPaths": bool(config.get("includeMediaPaths", True)),
        },
        config=config,
    )


def collect():
    config = load_config()
    ensure_ciphertalk_ready(config)
    state = read_json(
        STATE_PATH, {"initialized": False, "sessions": {}, "pending": []}
    )
    state["sessions"] = (
        state.get("sessions") if isinstance(state.get("sessions"), dict) else {}
    )
    state["pending"] = (
        state.get("pending") if isinstance(state.get("pending"), list) else []
    )
    schema_version = 1
    needs_baseline = (
        not state.get("initialized") or state.get("schemaVersion") != schema_version
    )
    session_data = call_ciphertalk(
        "list_sessions",
        {"offset": 0, "limit": int(config.get("sessionLimit", 500))},
        config=config,
    )
    sessions = session_data.get("items") or []
    pending_keys = {row.get("message_key") for row in state["pending"]}
    new_rows = []
    warnings = []
    collected_at = datetime.now().astimezone().isoformat()

    for session in sessions:
        session_id = str(session.get("sessionId") or "")
        if not session_id:
            continue
        last_time = int(session.get("lastTimestamp") or 0)
        previous = state["sessions"].get(session_id)
        try:
            if needs_baseline:
                data = get_messages(
                    session_id, int(config.get("baselineMessageLimit", 50)), config
                )
                messages = data.get("items") or []
                state["sessions"][session_id] = {
                    "lastTime": last_time,
                    "lastPreview": str(session.get("lastMessagePreview") or ""),
                    "unreadCount": int(session.get("unreadCount") or 0),
                    "recentKeys": [
                        message_key(session_id, message) for message in messages
                    ],
                }
                continue

            if previous and last_time <= int(previous.get("lastTime") or 0):
                continue

            data = get_messages(
                session_id, int(config.get("messageLimit", 200)), config
            )
            messages = data.get("items") or []
            known_keys = set((previous or {}).get("recentKeys") or [])
            current_keys = []
            for message in messages:
                key = message_key(session_id, message)
                current_keys.append(key)
                if key in known_keys or key in pending_keys:
                    continue
                if previous and int(message.get("timestamp") or 0) < int(
                    previous.get("lastTime") or 0
                ):
                    continue
                cursor = message.get("cursor") or {}
                media = message.get("media") or {}
                pending_keys.add(key)
                new_rows.append(
                    {
                        "message_key": key,
                        "session_id": session_id,
                        "create_time_raw": str(message.get("timestamp") or ""),
                        "local_time": local_time(message.get("timestamp")),
                        "direction": str(message.get("direction") or ""),
                        "sender_username": excel_safe(
                            sender_label(message.get("sender"), session)
                        ),
                        "type_raw": str(message.get("kind") or ""),
                        "content": excel_safe(message.get("text")),
                        "media_path": str(media.get("localPath") or ""),
                        "media_type": str(media.get("type") or ""),
                        "local_id": str(cursor.get("localId") or ""),
                        "server_id_text": str(message.get("messageId") or ""),
                        "sort_seq_text": str(cursor.get("sortSeq") or ""),
                        "collected_at": collected_at,
                        "source": "CipherTalk desktop MCP",
                    }
                )
            state["sessions"][session_id] = {
                "lastTime": last_time,
                "lastPreview": str(session.get("lastMessagePreview") or ""),
                "unreadCount": int(session.get("unreadCount") or 0),
                "recentKeys": current_keys[: int(config.get("messageLimit", 200))],
            }
        except Exception as error:
            if getattr(error, "code", "") == "SESSION_NOT_FOUND":
                preview = str(session.get("lastMessagePreview") or "")
                changed = previous and (
                    last_time > int(previous.get("lastTime") or 0)
                    or preview != str(previous.get("lastPreview") or "")
                )
                key = preview_key(session_id, session)
                if (
                    not needs_baseline
                    and changed
                    and preview
                    and key not in pending_keys
                ):
                    pending_keys.add(key)
                    new_rows.append(
                        {
                            "message_key": key,
                            "session_id": session_id,
                            "create_time_raw": str(last_time or ""),
                            "local_time": local_time(last_time),
                            "direction": (
                                "in"
                                if int(session.get("unreadCount") or 0)
                                > int(previous.get("unreadCount") or 0)
                                else "unknown"
                            ),
                            "sender_username": excel_safe(
                                session.get("displayName")
                                if session.get("kind") != "group"
                                else "群聊成员（预览未提供）"
                            ),
                            "type_raw": "preview",
                            "content": excel_safe(preview),
                            "media_path": "",
                            "media_type": "",
                            "local_id": "",
                            "server_id_text": "",
                            "sort_seq_text": "",
                            "collected_at": collected_at,
                            "source": "CipherTalk session preview",
                        }
                    )
                state["sessions"][session_id] = {
                    "lastTime": last_time,
                    "lastPreview": preview,
                    "unreadCount": int(session.get("unreadCount") or 0),
                    "recentKeys": [],
                    "previewFallback": True,
                }
                warnings.append(
                    {
                        "sessionHash": hashlib.sha256(
                            session_id.encode()
                        ).hexdigest()[:10],
                        "code": "SESSION_NOT_FOUND",
                    }
                )
            else:
                warnings.append(
                    {
                        "sessionHash": hashlib.sha256(
                            session_id.encode()
                        ).hexdigest()[:10],
                        "code": getattr(error, "code", "ERROR"),
                    }
                )

    state["initialized"] = True
    state["schemaVersion"] = schema_version
    state["updatedAt"] = collected_at
    state["pending"].extend(new_rows)
    state["pending"].sort(key=lambda row: int(row.get("create_time_raw") or 0))
    output = {
        "ok": True,
        "data": {"messages": state["pending"]},
        "meta": {
            "total": len(state["pending"]),
            "newlyCollected": len(new_rows),
            "sessionsScanned": len(sessions),
            "warningCount": len(warnings),
            "initialized": True,
        },
    }
    atomic_write_json(STATE_PATH, state)
    atomic_write_json(OUTPUT_PATH, output)
    atomic_write_json(LOG_DIR / "collector_warnings.json", warnings)
    log_status(
        "collector_status.json",
        {"ok": True, **output["meta"], "updatedAt": collected_at},
    )
    return output


def main():
    try:
        output = collect()
        print(
            json.dumps(
                {"ok": True, "messageCount": len(output["data"]["messages"])}
            )
        )
        return 0
    except Exception as error:
        log_status(
            "collector_status.json",
            {
                "ok": False,
                "errorCode": getattr(error, "code", "ERROR"),
                "error": str(error),
            },
        )
        atomic_write_json(
            OUTPUT_PATH,
            {
                "ok": False,
                "error": {
                    "code": getattr(error, "code", "ERROR"),
                    "message": str(error),
                },
            },
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
