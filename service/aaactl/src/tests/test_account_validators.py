import pytest

import account.validators as validators


def test_validate_password():
    assert validators.validate_password("12345678") == "12345678"
    with pytest.raises(validators.ValidationError):
        validators.validate_password("test")
