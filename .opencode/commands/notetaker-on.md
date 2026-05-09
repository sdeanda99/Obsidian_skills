---
description: Enable automatic Obsidian note capture
---
!`python3 -c "
import json, os
p = os.path.expanduser('~/.config/opencode/obsidian_note_logger_state.json')
s = json.loads(open(p).read()) if os.path.exists(p) else {}
s['enabled'] = True
open(p,'w').write(json.dumps(s, indent=2))
count = s.get('notes_written', 0)
print(f'enabled=true notes_written={count}')
"`

The note logger is now ON. It will capture decisions, patterns, and learnings when the session next goes idle. Confirm this to the user in one sentence.
