import json
import os
from typing import Set
from datetime import datetime, timedelta

class JudgmentStorage:
    def __init__(self, storage_file: str = None):
        self.storage_file = storage_file or os.getenv('STORAGE_FILE', 'sent_judgments.json')
        # Ensure parent directory exists if a custom path is used
        parent_dir = os.path.dirname(os.path.abspath(self.storage_file))
        if parent_dir and not os.path.exists(parent_dir):
            try:
                os.makedirs(parent_dir, exist_ok=True)
            except Exception as e:
                print(f"Error creating storage directory: {e}")
        self.sent_judgments: Set[str] = self._load_sent_judgments()

    def _load_sent_judgments(self) -> Set[str]:
        """Load previously sent judgment identifiers from file"""
        if not os.path.exists(self.storage_file):
            return set()

        try:
            with open(self.storage_file, 'r') as f:
                data = json.load(f)
                # Expecting a list of strings (judgment IDs)
                if isinstance(data, list):
                    return set(data)
                else:
                    # If format is different, try to extract IDs
                    return set()
        except Exception as e:
            print(f"Error loading storage: {e}")
            return set()

    def _save_sent_judgments(self):
        """Save sent judgment identifiers to file"""
        try:
            # Optionally, keep only judgments from last 30 days to prevent infinite growth
            cutoff_date = datetime.now() - timedelta(days=30)
            # Note: We don't store timestamps in this simple version, so we keep all.
            # For a more advanced version, we could store tuples (id, timestamp) and filter.
            with open(self.storage_file, 'w') as f:
                json.dump(list(self.sent_judgments), f, indent=2)
        except Exception as e:
            print(f"Error saving storage: {e}")

    def is_judgment_sent(self, judgment_id: str) -> bool:
        """Check if judgment has already been sent"""
        return judgment_id in self.sent_judgments

    def mark_judgment_sent(self, judgment_id: str):
        """Mark judgment as sent"""
        self.sent_judgments.add(judgment_id)
        self._save_sent_judgments()

    def get_sent_count(self) -> int:
        """Get count of sent judgments"""
        return len(self.sent_judgments)