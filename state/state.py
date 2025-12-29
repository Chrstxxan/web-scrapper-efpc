'''
modulo que basicamente é a memoria do sistema, tudo que ele "lembra" é por causa desse arquivo
'''
from pathlib import Path

class State:
    def __init__(self, data_dir: Path):
        self.visited_pages_path = data_dir / "visited_pages.txt"
        self.visited_files_path = data_dir / "visited_files.txt"
        self.hashes_path = data_dir / "hashes.txt"
        self.failed_path = data_dir / "failed.txt"
        self.queue_path = data_dir / "queue.txt"

        self.visited_pages = self._load(self.visited_pages_path)
        self.visited_files = self._load(self.visited_files_path)
        self.hashes = self._load(self.hashes_path)
        self.failed = self._load(self.failed_path)
        self.queue = self._load(self.queue_path)

    def _load(self, path: Path) -> set:
        if not path.exists():
            return set()
        return set(path.read_text(encoding="utf-8").splitlines())

    def _append(self, path: Path, value: str):
        with open(path, "a", encoding="utf-8") as f:
            f.write(value + "\n")

    def save_visited_page(self, url: str):
        if url not in self.visited_pages:
            self.visited_pages.add(url)
            self._append(self.visited_pages_path, url)

    def save_visited_file(self, url: str):
        if url not in self.visited_files:
            self.visited_files.add(url)
            self._append(self.visited_files_path, url)

    def save_hash(self, h: str):
        if h not in self.hashes:
            self.hashes.add(h)
            self._append(self.hashes_path, h)

    def save_failed(self, url: str):
        if url not in self.failed:
            self.failed.add(url)
            self._append(self.failed_path, url)

    def save_queue(self, queue: list[str]):
        self.queue = set(queue)
        self.queue_path.write_text("\n".join(queue), encoding="utf-8")
