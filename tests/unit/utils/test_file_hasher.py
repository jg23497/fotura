import hashlib

from fotura.utils.file_hasher import hash_file


class TestHashFile:
    def test_returns_hex_string(self, tmp_path):
        path = tmp_path / "test.bin"
        path.write_bytes(b"hello world")

        result = hash_file(path)

        assert isinstance(result, str)
        assert len(result) == 32  # 16 bytes = 32 hex chars

    def test_hash_is_deterministic(self, tmp_path):
        path = tmp_path / "test.bin"

        path.write_bytes(b"hello world")

        assert hash_file(path) == hash_file(path)

    def test_different_content_produces_different_hash(self, tmp_path):
        path_a = tmp_path / "a.bin"
        path_b = tmp_path / "b.bin"

        path_a.write_bytes(b"content a")
        path_b.write_bytes(b"content b")

        assert hash_file(path_a) != hash_file(path_b)

    def test_matches_manual_blake2b_computation(self, tmp_path):
        data = b"some test data for hashing"
        path = tmp_path / "test.bin"
        path.write_bytes(data)

        expected = hashlib.blake2b(data, digest_size=16).hexdigest()
        assert hash_file(path) == expected

    def test_handles_empty_file(self, tmp_path):
        path = tmp_path / "empty.bin"
        path.write_bytes(b"")

        result = hash_file(path)
        expected = hashlib.blake2b(b"", digest_size=16).hexdigest()

        assert result == expected
