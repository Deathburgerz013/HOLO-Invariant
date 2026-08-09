import unittest
import tempfile
import os
import json

from holosim.core import HoloChain


class TestHoloChain(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.test_dir, "test_memory.jsonl")
        self.chain = HoloChain(file_path=self.test_file)

    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
        lock_file = self.test_file + ".lock"
        if os.path.exists(lock_file):
            os.remove(lock_file)
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


    def test_correction_preserves_raw_history_and_updates_effective_view(self):
        original = self.chain.append("Claim: ratio is 0.83")
        self.chain.append("Unrelated entry")
        correction = self.chain.correct(
            original["idx"],
            "Claim: ratio is 0.71",
            reason="Recomputed from raw source",
        )

        raw = self.chain.load_and_verify()
        self.assertEqual(len(raw), 3)
        self.assertEqual(raw[0]["content"], "Claim: ratio is 0.83")
        self.assertEqual(json.loads(raw[2]["content"])["corrects_hash"], original["hash"])

        effective = self.chain.get_effective_state()
        self.assertEqual(len(effective), 2)
        corrected = next(row for row in effective if row["idx"] == original["idx"])
        self.assertEqual(corrected["content"], "Claim: ratio is 0.71")
        self.assertEqual(corrected["corrected_by"], correction["idx"])
        self.assertEqual(corrected["reason"], "Recomputed from raw source")

    def test_latest_correction_wins_without_erasing_correction_history(self):
        original = self.chain.append("Claim: v1")
        first = self.chain.correct(original["idx"], "Claim: v2", reason="first fix")
        second = self.chain.correct(original["idx"], "Claim: v3", reason="second fix")

        effective = self.chain.get_effective_state()[0]
        self.assertEqual(effective["content"], "Claim: v3")
        self.assertEqual(effective["correction_history"], [first["idx"], second["idx"]])

        history = self.chain.get_corrections(original["idx"])
        self.assertEqual([item["reason"] for item in history], ["first fix", "second fix"])
        self.assertEqual([item["content"] for item in history], ["Claim: v2", "Claim: v3"])

    def test_correction_requires_existing_original_and_reason(self):
        with self.assertRaises(ValueError):
            self.chain.correct(999, "replacement", reason="missing target")

        original = self.chain.append("Claim: X")
        with self.assertRaises(ValueError):
            self.chain.correct(original["idx"], "Claim: Y", reason="   ")

        correction = self.chain.correct(original["idx"], "Claim: Y", reason="evidence")
        with self.assertRaises(ValueError):
            self.chain.correct(correction["idx"], "Claim: Z", reason="invalid target")

    def test_malformed_correction_reference_fails_closed(self):
        original = self.chain.append("Claim: original")
        self.chain.append({
            "_holo_record_type": "holo_correction",
            "version": 1,
            "corrects_idx": original["idx"],
            "corrects_hash": "0" * 64,
            "reason": "invalid binding",
            "replacement": "Claim: replacement",
        })

        with self.assertRaisesRegex(ValueError, "target hash mismatch"):
            self.chain.get_effective_state()

    def test_correction_replacement_must_be_json_serializable(self):
        original = self.chain.append("Claim: original")
        with self.assertRaises(TypeError):
            self.chain.correct(original["idx"], object(), reason="invalid replacement")

    def test_revalidation_marks_current_effective_claim(self):
        original = self.chain.append("Claim: ratio is 0.71")
        receipt = self.chain.revalidate(
            original["idx"],
            "HELD",
            evidence="fixture:ratio-v2",
            method="recomputed from raw source",
        )

        checks = self.chain.get_revalidations(original["idx"])
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0]["idx"], receipt["idx"])
        self.assertEqual(checks[0]["outcome"], "HELD")
        self.assertTrue(checks[0]["current"])

        claim = self.chain.get_claim_index()[0]
        self.assertEqual(claim["status"], "HELD")
        self.assertEqual(claim["revalidated_by"], receipt["idx"])

    def test_never_checked_claim_remains_unchecked(self):
        self.chain.append("Claim: awaiting first check")

        claim = self.chain.get_claim_index()[0]
        self.assertEqual(claim["status"], "UNCHECKED")
        self.assertEqual(claim["revalidation_history"], [])

    def test_correction_makes_prior_revalidation_stale_until_rechecked(self):
        original = self.chain.append("Claim: v1")
        old_check = self.chain.revalidate(
            original["idx"], "HELD", evidence="fixture:v1", method="comparison"
        )
        correction = self.chain.correct(
            original["idx"], "Claim: v2", reason="new source evidence"
        )

        checks = self.chain.get_revalidations(original["idx"])
        self.assertEqual(checks[0]["idx"], old_check["idx"])
        self.assertFalse(checks[0]["current"])
        claim = self.chain.get_claim_index()[0]
        self.assertEqual(claim["status"], "STALE")
        self.assertEqual(claim["corrected_by"], correction["idx"])

        new_check = self.chain.revalidate(
            original["idx"], "HELD", evidence="fixture:v2", method="comparison"
        )
        checks = self.chain.get_revalidations(original["idx"])
        self.assertEqual([check["current"] for check in checks], [False, True])
        claim = self.chain.get_claim_index()[0]
        self.assertEqual(claim["status"], "HELD")
        self.assertEqual(claim["revalidated_by"], new_check["idx"])
        self.assertEqual(
            claim["revalidation_history"], [old_check["idx"], new_check["idx"]]
        )

    def test_latest_current_revalidation_wins_without_erasing_history(self):
        original = self.chain.append("Claim: testable")
        first = self.chain.revalidate(
            original["idx"], "UNAVAILABLE", evidence="tool offline", method="lookup"
        )
        second = self.chain.revalidate(
            original["idx"], "FAILED", evidence="fixture:mismatch", method="replay"
        )

        claim = self.chain.get_claim_index()[0]
        self.assertEqual(claim["status"], "FAILED")
        self.assertEqual(claim["revalidated_by"], second["idx"])
        self.assertEqual(
            claim["revalidation_history"], [first["idx"], second["idx"]]
        )

    def test_revalidation_requires_original_and_complete_inputs(self):
        original = self.chain.append("Claim: original")
        correction = self.chain.correct(original["idx"], "Claim: fixed", reason="fix")

        with self.assertRaises(ValueError):
            self.chain.revalidate(999, "HELD", evidence="x", method="test")
        with self.assertRaises(ValueError):
            self.chain.revalidate(
                correction["idx"], "HELD", evidence="x", method="test"
            )
        with self.assertRaises(ValueError):
            self.chain.revalidate(
                original["idx"], "UNKNOWN", evidence="x", method="test"
            )
        with self.assertRaises(ValueError):
            self.chain.revalidate(
                original["idx"], "HELD", evidence="   ", method="test"
            )

    def test_malformed_revalidation_reference_fails_closed(self):
        original = self.chain.append("Claim: original")
        self.chain.append({
            "_holo_record_type": "holo_revalidation",
            "version": 1,
            "target_idx": original["idx"],
            "target_hash": "0" * 64,
            "subject_hash": "0" * 64,
            "subject_correction_idx": None,
            "outcome": "HELD",
            "method": "comparison",
            "evidence": "fixture:invalid",
        })

        with self.assertRaisesRegex(ValueError, "target hash mismatch"):
            self.chain.get_claim_index()

    def test_malformed_revalidation_subject_hash_fails_closed(self):
        original = self.chain.append("Claim: original")
        self.chain.append({
            "_holo_record_type": "holo_revalidation",
            "version": 1,
            "target_idx": original["idx"],
            "target_hash": original["hash"],
            "subject_hash": "0" * 64,
            "subject_correction_idx": None,
            "outcome": "HELD",
            "method": "comparison",
            "evidence": "fixture:false-subject-binding",
        })

        with self.assertRaisesRegex(ValueError, "subject hash mismatch"):
            self.chain.get_claim_index()

if __name__ == "__main__":
    unittest.main()
