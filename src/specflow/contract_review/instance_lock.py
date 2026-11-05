"""An OS-held lock, never a PID file or evidence of adapter quiescence."""

import os
from pathlib import Path


class InstanceLock:
    def __init__(self, database_path: str):
        path = Path(database_path).resolve()
        if path.exists() and path.stat().st_nlink > 1:
            raise RuntimeError("Contract-review database must not have hard-link aliases")
        self.path = path.with_name(path.name + ".contract-review.lock")
        self._file = None

    def acquire(self):
        if self._file is not None:
            raise RuntimeError("Instance lock is already held")
        handle = self.path.open("a+b")
        try:
            if self.path.stat().st_size == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            handle.close()
            raise RuntimeError("Another contract-review instance owns this database") from None
        self._file = handle

    def release(self):
        if self._file is not None:
            self._file.close()
            self._file = None
