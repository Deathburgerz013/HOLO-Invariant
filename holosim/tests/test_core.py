import unittest
import tempfile
import os
import json
from holosim.core import HoloChain

class TestHoloChain(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test_holo_memory.jsonl")
        self.chain = HoloChain(file_path=self.test_file)

    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
        os.rmdir(self.temp_dir)

    def test_append_and_replay(self):
        """Test basic append + replay integrity"""
        self.chain.append("Test entry 1")
        self.chain.append("Test entry 2")
        
        entries = self.chain.replay()
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["content"], "Test entry 1")
        self.assertEqual(entries[1]["content"], "Test entry 2")

    def test_tamper_detection(self):
        """Core invariant: Any modification must fail verification"""
        self.chain.append("Tamper test entry")
        
        # Tamper the file directly
        with open(self.test_file, "r+", encoding="utf-8") as f:
            content = f.read()
            # Change one character in the last hash
            tampered = content[:-10] + "X" + content[-9:]
            f.seek(0)
            f.write(tampered)
            f.truncate()
        
        # Replay must fail
        with self.assertRaises(ValueError) as cm:
            self.chain.replay()
        self.assertIn("Hash mismatch", str(cm.exception))

    def test_empty_chain(self):
        """Handle empty chain gracefully"""
        entries = self.chain.replay()
        self.assertEqual(len(entries), 0)

if __name__ == "__main__":
    unittest.main()