import json
import os
import requests
from typing import Set, List
from datetime import datetime, timedelta

class JudgmentStorage:
    def __init__(self, storage_file: str = None):
        self.storage_file = storage_file or os.getenv('STORAGE_FILE', 'sent_judgments.json')
        self.kvdb_bucket = os.getenv('KVDB_BUCKET', '').strip()
        # Ensure parent directory exists if a custom path is used
        parent_dir = os.path.dirname(os.path.abspath(self.storage_file))
        if parent_dir and not os.path.exists(parent_dir):
            try:
                os.makedirs(parent_dir, exist_ok=True)
            except Exception as e:
                print(f"Error creating storage directory: {e}")
        self.sent_judgments: Set[str] = self._load_sent_judgments()

    def _load_sent_judgments(self) -> Set[str]:
        """Load previously sent judgment identifiers from file and remote KV if configured"""
        loaded = set()
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        loaded.update(data)
            except Exception as e:
                print(f"Error loading local storage: {e}")

        # Check cloud KV if configured (persists across Render container restarts)
        if self.kvdb_bucket:
            try:
                url = f"https://kvdb.io/{self.kvdb_bucket}/dhc_sent_judgments"
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    remote_data = resp.json()
                    if isinstance(remote_data, list):
                        loaded.update(remote_data)
            except Exception as e:
                print(f"Error loading from KVdb: {e}")

        return loaded

    def _save_sent_judgments(self):
        """Save sent judgment identifiers to file and remote KV"""
        # 1. Save local
        try:
            with open(self.storage_file, 'w') as f:
                json.dump(list(self.sent_judgments), f, indent=2)
        except Exception as e:
            print(f"Error saving local storage: {e}")

        # 2. Save cloud KV if configured
        if self.kvdb_bucket:
            try:
                url = f"https://kvdb.io/{self.kvdb_bucket}/dhc_sent_judgments"
                requests.post(url, json=list(self.sent_judgments), timeout=5)
            except Exception as e:
                print(f"Error syncing to KVdb: {e}")

    def is_judgment_sent(self, judgment_id: str) -> bool:
        """Check if judgment has already been sent"""
        return judgment_id in self.sent_judgments

    def mark_judgment_sent(self, judgment_id: str):
        """Mark judgment as sent"""
        self.sent_judgments.add(judgment_id)
        self._save_sent_judgments()

    def mark_all_seen(self, judgment_ids: List[str]):
        """Mark a batch of judgment identifiers as seen"""
        for j_id in judgment_ids:
            self.sent_judgments.add(j_id)
        self._save_sent_judgments()

    def get_sent_count(self) -> int:
        """Get count of sent judgments"""
        return len(self.sent_judgments)