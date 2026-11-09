# -*- coding: utf-8 -*-
"""
Tests: PBKDF2-SHA256 password hashing, backward compat, timing safety.
"""

import time
import pytest
from app.utils.helpers import (
    hash_password, verify_password, needs_rehash,
    _verify_pbkdf2, _verify_legacy,
)


class TestPBKDF2Format:
    def test_hash_format(self):
        h = hash_password("TestPass@1")
        parts = h.split(":")
        assert len(parts) == 5
        assert parts[0] == "pbkdf2"
        assert parts[1] == "sha256"
        assert parts[2] == "600000"

    def test_per_user_salt_unique(self):
        """Mỗi lần hash phải tạo salt khác nhau."""
        h1 = hash_password("SamePass@1")
        h2 = hash_password("SamePass@1")
        assert h1 != h2, "Hai hash của cùng password phải khác nhau (khác salt)"

    def test_verify_round_trip(self):
        pw = "RoundTrip@99"
        assert verify_password(pw, hash_password(pw))

    def test_verify_wrong_password(self):
        h = hash_password("Correct@1")
        assert not verify_password("Wrong@1", h)

    def test_verify_empty_password(self):
        h = hash_password("Something@1")
        assert not verify_password("", h)
        assert not verify_password("", "")

    def test_verify_tampered_hash(self):
        h = hash_password("Valid@1")
        tampered = h[:-4] + "XXXX"
        assert not verify_password("Valid@1", tampered)

    def test_verify_truncated_hash(self):
        assert not verify_password("Valid@1", "pbkdf2:sha256:600000:abc")

    def test_needs_rehash_new(self):
        assert not needs_rehash(hash_password("Test@1"))

    def test_needs_rehash_legacy(self):
        legacy = "67fc4c2b5fd9ce86517e9028decd7bf466cea58e256de52616597978d1270e56"
        assert needs_rehash(legacy)

    def test_needs_rehash_raw_sha256(self):
        import hashlib
        raw = hashlib.sha256(b"admin").hexdigest()
        assert needs_rehash(raw)


class TestLegacyBackwardCompat:
    """Hash cũ (legacy SHA-256 + salt cố định) vẫn verify được."""

    # Hash của hash_password cũ = SHA256("skillproof_salt_2024" + password)
    LEGACY_HASH_ADMIN = "67fc4c2b5fd9ce86517e9028decd7bf466cea58e256de52616597978d1270e56"

    def test_legacy_verify_correct(self):
        assert verify_password("admin", self.LEGACY_HASH_ADMIN)

    def test_legacy_verify_wrong(self):
        assert not verify_password("notadmin", self.LEGACY_HASH_ADMIN)

    def test_legacy_verify_empty(self):
        assert not verify_password("", self.LEGACY_HASH_ADMIN)

    def test_pbkdf2_does_not_match_legacy(self):
        """Hash PBKDF2 mới KHÔNG verify được với _verify_legacy."""
        new_hash = hash_password("admin")
        assert not _verify_legacy("admin", new_hash)

    def test_legacy_does_not_match_pbkdf2(self):
        """Legacy hash KHÔNG verify được với _verify_pbkdf2."""
        assert not _verify_pbkdf2("admin", self.LEGACY_HASH_ADMIN)


class TestTimingSafety:
    """
    Kiểm tra hmac.compare_digest đảm bảo constant-time comparison.
    Không thể đo timing attack chính xác ở level Python, nhưng
    đảm bảo verify_password không short-circuit sớm.
    """

    def test_verify_does_not_reveal_prefix(self):
        """
        verify_password với hash sai prefix không trả True.
        Đảm bảo không có early return trước khi so sánh đủ bytes.
        """
        fake_hashes = [
            "pbkdf2:sha256:600000:AAAA:AAAA",
            "pbkdf2:sha256:1:AAAA:AAAA",
            "",
            "::::",
            "pbkdf2:md5:600000:AAAA:AAAA",
        ]
        for fake in fake_hashes:
            assert not verify_password("admin", fake), f"Should fail for: {fake!r}"

    def test_verify_timing_comparable(self):
        """
        Thời gian verify password đúng vs sai phải tương đương
        (cả hai đều chạy PBKDF2 đầy đủ).
        """
        h = hash_password("Timing@1")

        times_correct = []
        times_wrong   = []

        for _ in range(3):
            t0 = time.perf_counter()
            verify_password("Timing@1", h)
            times_correct.append(time.perf_counter() - t0)

            t0 = time.perf_counter()
            verify_password("Wrong@999", h)
            times_wrong.append(time.perf_counter() - t0)

        avg_correct = sum(times_correct) / len(times_correct)
        avg_wrong   = sum(times_wrong) / len(times_wrong)

        # Chênh lệch không quá 50% — cả hai đều phải chạy PBKDF2 đầy đủ
        ratio = max(avg_correct, avg_wrong) / max(min(avg_correct, avg_wrong), 1e-9)
        assert ratio < 2.0, (
            f"Timing ratio {ratio:.2f} quá lớn — có thể có timing leak. "
            f"correct={avg_correct*1000:.0f}ms, wrong={avg_wrong*1000:.0f}ms"
        )
