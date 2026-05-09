---
description: Show current note logger status, note count, and last note written
---
!`python3 -c "
import json, os
p = os.path.expanduser('~/.config/opencode/obsidian_note_logger_state.json')
if not os.path.exists(p):
    print('status=unknown (state file missing)')
else:
    s = json.loads(open(p).read())
    enabled = s.get('enabled', True)
    count = s.get('notes_written', 0)
    last = s.get('last_note', 'none')
    last_at = s.get('last_write_at', 'never')
    print(f'enabled={enabled} notes_written={count} last_note={last} last_write_at={last_at}')
"`

Report the current note logger status to the user based on the output above. Keep it brief.
