import json
import time
from pathlib import Path

_LOG_PATH = Path(__file__).resolve().parents[3] / "debug-02c2f3.log"


def agent_log(hypothesis_id, location, message, data=None):
    # #region agent log
    try:
        record = {
            "sessionId": "02c2f3",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data or {},
            "timestamp": int(time.time() * 1000),
        }
        with _LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str) + "\n")
    except Exception:
        pass
    # #endregion
