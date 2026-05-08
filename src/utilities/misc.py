from datetime import datetime, timezone
import time

# Helper: Pause execution until the specified UTC datetime.
def sleep_until(target_time, chunk_seconds=30):
    """Pause until target_time (UTC) in small chunks for responsiveness."""
    if target_time.tzinfo is None:
        target_time = target_time.replace(tzinfo=timezone.utc)
    while True:
        now = datetime.now(timezone.utc)
        remaining = (target_time - now).total_seconds()
        if remaining <= 0:
            break
        time.sleep(min(remaining, chunk_seconds))