import unittest
import tempfile
import os

from holosim.core import HoloChain


class TestHoloChain(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.test_dir, "test_memory.jsonl")
        self.chain = HoloChain(file_path=self.test_file)

    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
        os.rmdir(self.test_dir)

    def test_append_and_verify(self):
        """Basic append + verify works"""
        entry = self.chain.append("Test entry")
        self.assertEqual(entry["idx"], 1)
        entries = self.chain.load_and_verify()
        self.assertEqual(len(entries), 1)

    def test_density_stats(self):
        """Density stats calculate correctly"""
        self.chain.append("plain text")
        self.chain.append({"key": "value"}, compress=True)
        stats = self.chain.get_density_stats()
        self.assertGreaterEqual(stats["total_entries"], 2)

    def test_tamper_detection(self):
        """Core invariant: Any modification must fail verification"""
        self.chain.append("Tamper test entry")
        # Tamper the file directly
        with open(self.test_file, "r+", encoding="utf-8") as f:
            content = f.read()
            pos = content.rfind('"hash":')
            if pos != -1:
                tampered = content[:pos + 20] + "X" + content[pos + 21:]
                f.seek(0)
                f.write(tampered)
                f.truncate()
        with self.assertRaises(ValueError):
            self.chain.load_and_verify()


if __name__ == "__main__":
    unittest.main()