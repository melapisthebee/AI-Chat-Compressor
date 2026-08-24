# gui/components/watcher.py
import time
from PyQt6.QtCore import QThread, pyqtSignal
from engine.discovery import scan_all_conversations_recursive

class PassiveFolderWatcherThread(QThread):
    """
    Polls LM Studio conversation subdirectories every N seconds.
    Emits chat_detected signal whenever a new file or modification occurs.
    """
    chat_detected = pyqtSignal(dict)       # Emits single updated conversation metadata
    scan_complete = pyqtSignal(list)       # Emits full list on initial scan

    def __init__(self, poll_interval: float = 3.0):
        super().__init__()
        self.poll_interval = poll_interval
        self._running = True
        self._tracked_mtimes = {}

    def stop(self):
        self._running = False

    def run(self):
        # Initial cold scan on startup
        initial_chats = scan_all_conversations_recursive()
        for chat in initial_chats:
            self._tracked_mtimes[chat["path"]] = chat["last_updated"]
        self.scan_complete.emit(initial_chats)

        # Passive polling loop
        while self._running:
            time.sleep(self.poll_interval)
            current_chats = scan_all_conversations_recursive()

            for chat in current_chats:
                path = chat["path"]
                last_mtime = chat["last_updated"]

                # Check if file is newly discovered or modified since last cycle
                if path not in self._tracked_mtimes or last_mtime > self._tracked_mtimes[path]:
                    self._tracked_mtimes[path] = last_mtime
                    self.chat_detected.emit(chat)
