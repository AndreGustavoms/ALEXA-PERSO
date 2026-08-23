import tempfile
import unittest
from pathlib import Path

from assistant_runtime.permission_store import PermissionStore


class PermissionStoreTests(unittest.TestCase):
    def test_persists_acceptance_and_revocation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            file_path = Path(directory) / "permissions.json"
            store = PermissionStore(file_path)

            self.assertFalse(store.is_accepted())
            accepted = store.set_accepted(True)
            self.assertTrue(accepted["accepted"])
            self.assertTrue(PermissionStore(file_path).is_accepted())

            store.set_accepted(False)
            self.assertFalse(PermissionStore(file_path).is_accepted())


if __name__ == "__main__":
    unittest.main()
