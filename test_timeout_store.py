import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from timeout_store import TimeoutStore


class TimeoutStoreTest(unittest.TestCase):
    def test_creates_database_and_restores_pending_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "sas.db"
            expires_at = datetime.now(timezone.utc) + timedelta(days=1)

            store = TimeoutStore(path)
            store.save(123, 456, expires_at, "manual")

            self.assertTrue(path.exists())
            self.assertTrue(store.is_pending(123, 456))
            pending = store.pending()
            self.assertEqual(len(pending), 1)
            self.assertEqual(pending[0].guild_id, 123)
            self.assertEqual(pending[0].user_id, 456)
            self.assertEqual(pending[0].source, "manual")

            self.assertTrue(store.complete(123, 456))
            self.assertFalse(store.complete(123, 456))
            self.assertFalse(store.is_pending(123, 456))
            store.close()


if __name__ == "__main__":
    unittest.main()
