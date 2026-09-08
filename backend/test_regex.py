import re
from enum import Enum

class ChatIntent(str, Enum):
    GENERATE_SCRIPT = "generate_script"
    REGENERATE_SCRIPT = "regenerate_script"

INTENT_PATTERNS = {
    ChatIntent.REGENERATE_SCRIPT: [
        r"(?:generate|regenerate)\s+script",
        r"(?:write|rewrite)\s+script",
        r"(?:create|make)\s+script",
        r"redo\s+script",
        r"start\s+over",
    ],
}

message = "Write a 3-beat script about a futuristic cyberpunk coffee brand."

for intent, patterns in INTENT_PATTERNS.items():
    for pattern in patterns:
        if re.search(pattern, message, re.IGNORECASE):
            print("MATCH:", intent, "PATTERN:", pattern)
            break
else:
    print("NO MATCH")
