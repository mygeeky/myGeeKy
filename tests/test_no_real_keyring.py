"""No test reaches the system keyring: whatever asks gets an empty in-memory one (conftest._no_real_keyring)."""


def test_the_keyring_in_a_test_is_empty_and_in_memory():
    import keyring
    from mygeeky import wisep
    assert type(keyring.get_keyring()).__name__ == "Memory"
    assert wisep.get_key() is None                         # the maker's real key is never read
    keyring.set_password("mygeeky-test", "me", "x")
    assert keyring.get_password("mygeeky-test", "me") == "x"


def test_and_each_test_starts_empty_again():
    import keyring
    assert keyring.get_password("mygeeky-test", "me") is None
