def test_can_import_space_aces_bot() -> None:
    import space_aces_bot  # noqa: F401

    assert "space_aces_bot" in globals() or space_aces_bot is not None

