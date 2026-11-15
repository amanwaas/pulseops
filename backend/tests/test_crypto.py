import pytest
from app.core.encryption import EncryptionService


def test_encryption_roundtrip():
    service = EncryptionService()
    secret = "ghp_mySuperSecretWebhookToken1234567890!@#"
    encrypted = service.encrypt(secret)

    assert encrypted != secret
    assert isinstance(encrypted, str)

    decrypted = service.decrypt(encrypted)
    assert decrypted == secret


def test_encryption_tamper_detection():
    service = EncryptionService()
    secret = "sensitive-webhook-secret"
    encrypted = service.encrypt(secret)

    # Tamper with the ciphertext payload
    tampered = encrypted[:-4] + "AAAA"

    with pytest.raises(ValueError):
        service.decrypt(tampered)


def test_empty_string_handling():
    service = EncryptionService()
    assert service.encrypt("") == ""
    assert service.decrypt("") == ""
