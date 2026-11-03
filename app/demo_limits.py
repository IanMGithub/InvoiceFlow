import time
from collections import OrderedDict, deque


class SlidingWindowLimiter:
    """In-process sliding window. One worker does not share this with others."""

    def __init__(
        self,
        *,
        limit: int,
        window_seconds: int = 60,
        max_keys: int = 4096,
        clock=time.monotonic,
    ):
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if window_seconds < 1:
            raise ValueError("window_seconds must be at least 1")
        if max_keys < 1:
            raise ValueError("max_keys must be at least 1")
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._clock = clock
        self._hits: OrderedDict[str, deque] = OrderedDict()

    def check(self, key: str, now: float | None = None) -> tuple[bool, int]:
        current = self._clock() if now is None else now
        self._expire(current)

        hits = self._hits.get(key)
        if hits is None:
            if len(self._hits) >= self.max_keys:
                self._hits.popitem(last=False)
            hits = deque()
            self._hits[key] = hits

        self._hits.move_to_end(key)

        if len(hits) >= self.limit:
            retry_after = self.window_seconds
            if hits:
                retry_after = int(self.window_seconds - (current - hits[0]))
                if retry_after < 1:
                    retry_after = 1
            return False, retry_after

        hits.append(current)
        return True, 0

    def _expire(self, now: float) -> None:
        cutoff = now - self.window_seconds
        empty_keys = []
        for key, hits in self._hits.items():
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if not hits:
                empty_keys.append(key)
        for key in empty_keys:
            self._hits.pop(key, None)


def client_address(scope: dict) -> str:
    """Use the socket peer. Forwarded headers are not read here."""
    client = scope.get("client")
    if not client:
        return "unknown"
    host = client[0]
    if not isinstance(host, str) or host == "":
        return "unknown"
    return host
