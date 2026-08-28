from pathlib import Path


def test_first_login_reopens_incomplete_setup_and_keeps_logs_private() -> None:
    script = Path("system_files/usr/bin/spider-os-first-login").read_text(encoding="utf-8")

    assert "spider-os setup --status" in script
    assert '"complete"' in script
    assert "XDG_STATE_HOME" in script
    assert "/tmp/spider-setup.log" not in script
    assert "umask 077" in script
