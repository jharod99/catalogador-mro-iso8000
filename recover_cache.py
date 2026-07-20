import json
import re

log_path = r"C:\Users\EMILIO\.gemini\antigravity\brain\dd52f94a-f16c-47cc-bd9b-6513dbc5d8c0\.system_generated\logs\transcript_full.jsonl"

with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        step = json.loads(line)
        if "tool_calls" in step:
            for tc in step["tool_calls"]:
                args = tc.get("Arguments", {})
                if isinstance(args, dict) and "CodeContent" in args:
                    code = args["CodeContent"]
                    if "def cache_node" in code and "GOLDEN_RECORD_PATH" in code:
                        with open("recovered_cache.py", "w", encoding="utf-8") as out:
                            out.write(code)
                        print("Found in CodeContent!")
                        break
        if "content" in step:
            content = step["content"]
            if "def cache_node" in content and "GOLDEN_RECORD_PATH" in content:
                match = re.search(r'def cache_node.*?return \{"items": items, "estado_global": estado_global, "mensaje_global": mensaje_global\}', content, re.DOTALL)
                if match:
                    with open("recovered_cache.py", "w", encoding="utf-8") as out:
                        out.write(match.group(0))
                    print("Found in content!")
                    break

print("Finished search.")
