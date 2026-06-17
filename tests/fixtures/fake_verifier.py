import json
import sys


packet = json.load(sys.stdin)
force = packet.get("force", "PASS")
if force == "PASS":
    print(json.dumps({"status": "PASS", "reason": "forced PASS"}))
elif force == "FAIL":
    print(json.dumps({"status": "FAIL", "reason": "forced FAIL"}))
elif force == "ESCALATE":
    print(json.dumps({"status": "ESCALATE", "reason": "forced ESCALATE"}))
else:
    print(json.dumps({"status": "BAD", "reason": "invalid"}))
