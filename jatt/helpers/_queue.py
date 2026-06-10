# Copyright (c) 2025 JattDevs
# Licensed under the MIT License.
# This file is part of JattMusicBot


from collections import defaultdict, deque
import random
from typing import Union

from ._dataclass import Media, Track

MediaItem = Union[Media, Track]


class Queue:
    def __init__(self):
        self.queues:  dict[int, deque[MediaItem]] = defaultdict(deque)
        self._history: dict[int, deque[MediaItem]] = defaultdict(lambda: deque(maxlen=10))

    def add(self, chat_id: int, item: MediaItem) -> int:
        if any(t.id == item.id for t in self.queues[chat_id]):
            return len(self.queues[chat_id]) - 1
        self.queues[chat_id].append(item)
        return len(self.queues[chat_id]) - 1

    def check_item(self, chat_id: int, item_id: str) -> tuple[int, MediaItem | None]:
        """Check if an item with the given ID exists in the queue."""
        pos, track = next(
            (
                (i, track)
                for i, track in enumerate(list(self.queues[chat_id]))
                if track.id == item_id
            ),
            (-1, None),
        )
        return pos, track

    def force_add(
        self, chat_id: int, item: MediaItem, remove: int | bool = False
    ) -> None:
        """Replace the currently playing item with a new one."""
        self.remove_current(chat_id)
        self.queues[chat_id].appendleft(item)
        if remove:
            self.queues[chat_id].rotate(-remove)
            self.queues[chat_id].popleft()
            self.queues[chat_id].rotate(remove)

    def get_current(self, chat_id: int) -> MediaItem | None:
        """Return the currently playing item (first in queue), if any."""
        return self.queues[chat_id][0] if self.queues[chat_id] else None

    def get_next(self, chat_id: int, check: bool = False) -> MediaItem | None:
        q = self.queues[chat_id]
        if check:
            return q[1] if len(q) > 1 else None
        if not q:
            return None
        self._history[chat_id].append(q[0])
        q.popleft()
        return q[0] if q else None

    def get_previous(self, chat_id: int) -> MediaItem | None:
        h = self._history[chat_id]
        if not h:
            return None
        track = h.pop()
        self.queues[chat_id].appendleft(track)
        return track
        """Remove current item and return the next one, or None if empty."""
        if not self.queues[chat_id]:
            return None
        if check:
            return self.queues[chat_id][1] if len(self.queues[chat_id]) > 1 else None

    def get_queue(self, chat_id: int) -> list[MediaItem]:
        """Return the full queue including the currently playing item."""
        return list(self.queues[chat_id])

    def remove_current(self, chat_id: int) -> None:
        """Remove the currently playing item only (if exists)."""
        if self.queues[chat_id]:
            self.queues[chat_id].popleft()

    def clear(self, chat_id: int) -> None:
        """Clear the entire queue."""
        self.queues[chat_id].clear()

    def clear_keep_current(self, chat_id: int) -> int:
        """Clear all queued tracks except the currently playing one. Returns count removed."""
        q = self.queues[chat_id]
        if not q:
            return 0
        current = q[0]
        removed = len(q) - 1
        self.queues[chat_id] = deque([current])
        return removed

    def move(self, chat_id: int, from_pos: int, to_pos: int) -> bool:
        """Move a queued track from from_pos to to_pos (1-indexed, excludes currently playing).
        Returns False if positions are invalid or equal."""
        q = self.queues[chat_id]
        size = len(q)
        # Position 0 = currently playing; queued items are 1 .. size-1
        if from_pos < 1 or from_pos >= size or to_pos < 1 or to_pos >= size:
            return False
        if from_pos == to_pos:
            return False
        lst = list(q)
        item = lst.pop(from_pos)
        lst.insert(to_pos, item)
        self.queues[chat_id] = deque(lst)
        return True

    def skipto(self, chat_id: int, pos: int) -> "MediaItem | None":
        """Make pos the new current track (1-indexed). Returns new current or None."""
        q = self.queues[chat_id]
        if pos < 1 or pos >= len(q):
            return None
        lst = list(q)
        self.queues[chat_id] = deque(lst[pos:])
        return lst[pos]

    def shuffle(self, chat_id: int) -> int:
        """Shuffle all queued tracks except currently playing. Returns shuffled count."""
        q = self.queues[chat_id]
        if len(q) < 2:
            return 0
        current = q[0]
        rest = list(q)[1:]
        random.shuffle(rest)
        self.queues[chat_id] = deque([current] + rest)
        return len(rest)
        """Remove and return the queued track at pos (1-indexed, excludes currently playing).
        Returns None if pos is out of range."""
        q = self.queues[chat_id]
        size = len(q)
        if pos < 1 or pos >= size:
            return None
        lst = list(q)
        item = lst.pop(pos)
        self.queues[chat_id] = deque(lst)
        return item
