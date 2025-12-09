def test_generate_api_key(db, account_objects):
    assert account_objects.user.key_set.count() == 1
    assert account_objects.user.key_set.first().managed is True


def test_create_personal_org(db, account_objects):
    assert account_objects.user.personal_org


def test_create_user_config(db, account_objects):
    assert account_objects.user.user_settings
