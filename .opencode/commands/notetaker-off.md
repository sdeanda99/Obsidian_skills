---
description: Disable automatic Obsidian note capture
---
!`python3 -c "
import json, os
p = os.path.expanduser('~/.config/opencode/obsidian_note_logger_state.json')
s = json.loads(open(p).read()) if os.path.exists(p) else {}
s['enabled'] = False
open(p,'w').write(json.dumps(s, indent=2))
print('enabled=false')
"`

The note logger is now OFF. No notes will be written until /notetaker-on is run. Confirm this to the user in one sentence.
