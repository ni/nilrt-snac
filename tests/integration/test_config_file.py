"""Tests for the _ConfigFile helper."""

from nilrt_snac._configs._config_file import _ConfigFile


def test_contains_anchors_match_any_line(tmp_path):
    path = tmp_path / "test.conf"
    path.write_text('INTERFACES=auto\nARGS="-a"\nARGS_wglv0="$ARGS --no-auto"\n')
    config = _ConfigFile(path)

    assert config.contains("^INTERFACES=")
    assert config.contains("^ARGS_wglv0=")
    assert config.contains('--no-auto"$')
    assert not config.contains("^--no-auto")
    assert not config.contains("^wglv0")
