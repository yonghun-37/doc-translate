from difflib import SequenceMatcher
from itertools import zip_longest


def compare(old: list[str], new: list[str], old_locations=None, new_locations=None) -> list[dict]:
    changes = []
    for op, a, b, c, d in SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if op == 'equal':
            continue
        for offset, (before, after) in enumerate(zip_longest(old[a:b], new[c:d])):
            index = (a if after is None else c) + offset
            locations = old_locations if after is None else new_locations
            changes.append({
                'op': 'added' if before is None else 'removed' if after is None else 'modified',
                'old': before if before is not None else '',
                'new': after if after is not None else '',
                'where': locations[index] if locations is not None else f'세그먼트 {index + 1}',
            })
    return changes
