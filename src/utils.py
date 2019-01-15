import hashlib


def sha1_hash2(a: str, b: str) -> str:
    h = hashlib.sha1(a.encode())
    h.update(b.encode())
    return h.hexdigest()
