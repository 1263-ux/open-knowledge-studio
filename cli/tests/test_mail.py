"""Tests for agent-to-agent mail: sender identity, body display, path safety."""

import pytest
from typer.testing import CliRunner


def _mail(tmp_path, monkeypatch, args, agent_id=None):
    from knowledge_studio import cli

    monkeypatch.setenv("OKS_ROOT", str(tmp_path))
    if agent_id is None:
        monkeypatch.delenv("OKS_AGENT_ID", raising=False)
    else:
        monkeypatch.setenv("OKS_AGENT_ID", agent_id)
    return CliRunner().invoke(cli.app, ["mail", *args])


def _sent(tmp_path):
    return sorted(p.name for p in (tmp_path / "mail" / "sent").iterdir())


def test_send_never_signs_as_human_without_identity(tmp_path, monkeypatch):
    """P9: an unset environment must not impersonate the human review gate."""
    monkeypatch.chdir(tmp_path)
    result = _mail(tmp_path, monkeypatch, ["send", "--body", "x"])

    assert result.exit_code == 0
    assert "human" not in _sent(tmp_path)
    inbox = list((tmp_path / "mail" / "inbox").rglob("*.md"))
    assert "from: human" not in inbox[0].read_text(encoding="utf-8")


def test_explicit_from_overrides_env(tmp_path, monkeypatch):
    result = _mail(
        tmp_path, monkeypatch, ["send", "--body", "x", "--from", "qoder"], agent_id="pi"
    )

    assert result.exit_code == 0
    assert _sent(tmp_path) == ["qoder"]


def test_env_identity_used_when_no_flag(tmp_path, monkeypatch):
    result = _mail(tmp_path, monkeypatch, ["send", "--body", "x"], agent_id="pi")

    assert result.exit_code == 0
    assert _sent(tmp_path) == ["pi"]


@pytest.mark.parametrize("agent_id", ["../evil", "a/b", "..", "a:b"])
def test_from_rejects_unsafe_path_component(tmp_path, monkeypatch, agent_id):
    """from_id is interpolated into mail/sent/{from_id}/."""
    result = _mail(
        tmp_path, monkeypatch, ["send", "--body", "x", "--from", agent_id], agent_id="pi"
    )

    assert result.exit_code == 1
    assert not (tmp_path / "mail" / "sent").exists()


@pytest.mark.parametrize("field", ["--to", "--type", "--priority"])
def test_frontmatter_fields_reject_injection(tmp_path, monkeypatch, field):
    """A newline would forge `from:` or set `read: true` to hide the mail."""
    result = _mail(
        tmp_path,
        monkeypatch,
        ["send", "--body", "x", field, "@all\nread: true"],
        agent_id="qoder",
    )

    assert result.exit_code == 1
    assert not list((tmp_path / "mail" / "inbox").rglob("*.md"))


def test_show_prints_body_without_marking_read(tmp_path, monkeypatch):
    _mail(
        tmp_path,
        monkeypatch,
        ["send", "--body", "needle body", "--title", "T"],
        agent_id="qoder",
    )
    slug = next((tmp_path / "mail" / "inbox").rglob("*.md")).stem

    shown = _mail(tmp_path, monkeypatch, ["show", slug], agent_id="qoder")
    counted = _mail(tmp_path, monkeypatch, ["count"], agent_id="qoder")

    assert shown.exit_code == 0
    assert "needle body" in shown.stdout
    assert "from: qoder" in shown.stdout
    assert counted.stdout.strip() == "1"


def test_read_marks_read_and_is_idempotent(tmp_path, monkeypatch):
    _mail(tmp_path, monkeypatch, ["send", "--body", "read: false"], agent_id="qoder")
    slug = next((tmp_path / "mail" / "inbox").rglob("*.md")).stem

    first = _mail(tmp_path, monkeypatch, ["read", slug], agent_id="qoder")
    second = _mail(tmp_path, monkeypatch, ["read", slug], agent_id="qoder")
    counted = _mail(tmp_path, monkeypatch, ["count"], agent_id="qoder")

    assert "Marked read" in first.stdout
    assert "Already read" in second.stdout
    assert counted.stdout.strip() == "0"
    # P7: the body's literal "read: false" must survive; only frontmatter changes.
    body = next((tmp_path / "mail" / "inbox").rglob("*.md")).read_text(encoding="utf-8")
    assert body.split("---", 2)[2].strip().endswith("read: false")


@pytest.mark.parametrize("command", ["show", "read"])
def test_mail_id_rejects_traversal(tmp_path, monkeypatch, command):
    # root/mail/inbox/{id}.md, so "../../secret" resolves to the KB root.
    (tmp_path / "secret.md").write_text("classified", encoding="utf-8")

    result = _mail(tmp_path, monkeypatch, [command, "../../secret"], agent_id="qoder")

    assert result.exit_code == 1
    assert "Invalid mail id" in result.stdout
    assert "classified" not in result.stdout


def test_mail_send_organizes_by_date(tmp_path, monkeypatch):
    """v0.6.16: oks mail send writes to inbox/{YYYY}/{MM}/{DD}/{slug}.md,
    not a flat inbox/, so a busy instance does not pile up hundreds of files."""
    result = _mail(
        tmp_path, monkeypatch,
        ["send", "--body", "x", "--from", "qoder"],
        agent_id="qoder",
    )
    assert result.exit_code == 0
    # slug = {YYYYMMDD}T{HHMMSS}-qoder; the 8-digit prefix drives the path.
    mails = list((tmp_path / "mail" / "inbox").rglob("*.md"))
    assert len(mails) == 1
    slug = mails[0].stem
    assert len(slug) >= 8 and slug[:8].isdigit()
    expected_dir = tmp_path / "mail" / "inbox" / slug[:4] / slug[4:6] / slug[6:8]
    assert mails[0].parent == expected_dir


def test_mail_migrate_moves_flat_to_date_dir(tmp_path, monkeypatch):
    """Legacy flat inbox mails are moved into date subdirs; idempotent."""
    # Seed a legacy flat mail at inbox/{slug}.md (pre-v0.6.16 layout).
    inbox = tmp_path / "mail" / "inbox"
    inbox.mkdir(parents=True)
    flat_slug = "20260101T120000-qoder"
    (inbox / f"{flat_slug}.md").write_text(
        "---\nfrom: qoder\nread: false\n---\n\n# hi\nbody\n",
        encoding="utf-8",
    )
    # First run moves the flat mail into the date subdir.
    r1 = _mail(tmp_path, monkeypatch, ["migrate"], agent_id="qoder")
    assert r1.exit_code == 0
    assert "Migrated" in r1.stdout
    flat_after = list((inbox).glob("*.md"))
    assert not flat_after  # no flat mails left at top level
    moved = list(inbox.rglob("*.md"))
    assert len(moved) == 1
    assert moved[0].stem == flat_slug
    assert moved[0].parent == inbox / "2026" / "01" / "01"
    # Second run is a no-op (idempotent).
    r2 = _mail(tmp_path, monkeypatch, ["migrate"], agent_id="qoder")
    assert r2.exit_code == 0
    assert "No flat mails" in r2.stdout
