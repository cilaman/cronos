from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from app.tools.sources import ToolSource, ToolSourceError, load_sources

ENV_VAR = "CRONOS_TOOL_SOURCES_PATH"


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    """Every test starts with no path override so the env-var test is the
    only one exercising that branch."""
    monkeypatch.delenv(ENV_VAR, raising=False)


def _write_yaml(path: Path, body: str) -> Path:
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# AC1 — Parsed list returned from a valid YAML file
# --------------------------------------------------------------------------


def test_load_sources_parses_valid_file(tmp_path):
    # Arrange
    cfg = _write_yaml(
        tmp_path / "sources.yml",
        """
        sources:
          - url: https://github.com/foo/bar.git
            branch: main
            enabled: true
            label: Bar tool
          - url: git@github.com:baz/qux.git
        """,
    )

    # Act
    sources = load_sources(cfg)

    # Assert
    assert len(sources) == 2
    assert sources[0] == ToolSource(
        url="https://github.com/foo/bar.git",
        branch="main",
        enabled=True,
        label="Bar tool",
    )


def test_load_sources_applies_field_defaults(tmp_path):
    # Arrange — only url provided; branch/label default None, enabled True.
    cfg = _write_yaml(
        tmp_path / "sources.yml",
        """
        sources:
          - url: https://github.com/foo/bar.git
        """,
    )

    # Act
    only = load_sources(cfg)[0]

    # Assert
    assert only.branch is None
    assert only.label is None
    assert only.enabled is True


def test_load_sources_preserves_enabled_false(tmp_path):
    # Arrange
    cfg = _write_yaml(
        tmp_path / "sources.yml",
        """
        sources:
          - url: https://github.com/foo/bar.git
            enabled: false
        """,
    )

    # Act
    only = load_sources(cfg)[0]

    # Assert — a disabled source must round-trip as disabled, not get dropped.
    assert only.enabled is False


def test_load_sources_empty_sources_key_returns_empty(tmp_path):
    # Arrange — file exists, valid YAML, but `sources:` is null.
    cfg = _write_yaml(tmp_path / "sources.yml", "sources:\n")

    # Act / Assert
    assert load_sources(cfg) == []


def test_load_sources_missing_sources_key_returns_empty(tmp_path):
    # Arrange — valid YAML mapping with no `sources` key at all.
    cfg = _write_yaml(tmp_path / "sources.yml", "other: value\n")

    # Act / Assert
    assert load_sources(cfg) == []


def test_load_sources_empty_file_returns_empty(tmp_path):
    # Arrange — completely empty file -> yaml.safe_load returns None.
    cfg = _write_yaml(tmp_path / "sources.yml", "")

    # Act / Assert
    assert load_sources(cfg) == []


# --------------------------------------------------------------------------
# AC2 — Invalid URL raises ToolSourceError
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_url",
    [
        pytest.param("", id="empty"),
        pytest.param("has space/repo.git", id="contains-space"),
        pytest.param("https://exa mple.com/x.git", id="space-in-host"),
        pytest.param("repo;rm -rf /", id="shell-metachar"),
        pytest.param("https://example.com/$(whoami).git", id="command-subst"),
        pytest.param("x" * 2049, id="too-long"),
    ],
)
def test_load_sources_rejects_invalid_url(tmp_path, bad_url):
    # Arrange — build the YAML via a mapping so weird URLs can't break parsing.
    import yaml

    cfg = tmp_path / "sources.yml"
    cfg.write_text(yaml.safe_dump({"sources": [{"url": bad_url}]}), encoding="utf-8")

    # Act / Assert
    with pytest.raises(ToolSourceError):
        load_sources(cfg)


def test_tool_source_constructor_rejects_invalid_url():
    # Act / Assert — validation happens at model construction, not just load.
    with pytest.raises(ToolSourceError):
        ToolSource(url="bad url with spaces")


def test_load_sources_one_bad_url_aborts_whole_load(tmp_path):
    # Arrange — first entry valid, second invalid; the load must fail entirely
    # rather than silently returning the partial good list.
    cfg = _write_yaml(
        tmp_path / "sources.yml",
        """
        sources:
          - url: https://github.com/foo/good.git
          - url: "bad url"
        """,
    )

    # Act / Assert
    with pytest.raises(ToolSourceError):
        load_sources(cfg)


def test_load_sources_wraps_non_url_validation_error(tmp_path):
    # Arrange — entry is a string, not a mapping; model_validate raises a
    # pydantic error that load_sources should wrap as ToolSourceError.
    cfg = _write_yaml(
        tmp_path / "sources.yml",
        """
        sources:
          - just-a-string
        """,
    )

    # Act / Assert
    with pytest.raises(ToolSourceError) as exc:
        load_sources(cfg)
    assert "Invalid tool source entry" in str(exc.value)


def test_load_sources_missing_url_field_raises(tmp_path):
    # Arrange — entry mapping without the required `url` field.
    cfg = _write_yaml(
        tmp_path / "sources.yml",
        """
        sources:
          - label: no url here
        """,
    )

    # Act / Assert
    with pytest.raises(ToolSourceError):
        load_sources(cfg)


# --------------------------------------------------------------------------
# AC3 — Missing file -> empty list
# --------------------------------------------------------------------------


def test_load_sources_missing_file_returns_empty(tmp_path):
    # Arrange — path that was never created.
    missing = tmp_path / "does-not-exist.yml"

    # Act / Assert
    assert load_sources(missing) == []


# --------------------------------------------------------------------------
# AC4 — CRONOS_TOOL_SOURCES_PATH env var overrides the path argument
# --------------------------------------------------------------------------


def test_env_var_overrides_path_argument(tmp_path, monkeypatch):
    # Arrange — the `path` argument points at a file with one source; the env
    # override points at a different file with two. We must read the override.
    arg_file = _write_yaml(
        tmp_path / "arg.yml",
        """
        sources:
          - url: https://github.com/foo/arg.git
        """,
    )
    override_file = _write_yaml(
        tmp_path / "override.yml",
        """
        sources:
          - url: https://github.com/foo/one.git
          - url: https://github.com/foo/two.git
        """,
    )
    monkeypatch.setenv(ENV_VAR, str(override_file))

    # Act
    sources = load_sources(arg_file)

    # Assert — we got the override file's two entries, not the arg file's one.
    assert [s.url for s in sources] == [
        "https://github.com/foo/one.git",
        "https://github.com/foo/two.git",
    ]


def test_env_var_override_to_missing_file_returns_empty(tmp_path, monkeypatch):
    # Arrange — arg file exists and is valid, but the override points at a
    # nonexistent path. The override wins, so the result must be empty.
    arg_file = _write_yaml(
        tmp_path / "arg.yml",
        """
        sources:
          - url: https://github.com/foo/arg.git
        """,
    )
    monkeypatch.setenv(ENV_VAR, str(tmp_path / "nope.yml"))

    # Act / Assert
    assert load_sources(arg_file) == []


def test_empty_env_var_falls_back_to_path_argument(tmp_path, monkeypatch):
    # Arrange — env var set but empty string is falsy, so the path arg is used.
    arg_file = _write_yaml(
        tmp_path / "arg.yml",
        """
        sources:
          - url: https://github.com/foo/arg.git
        """,
    )
    monkeypatch.setenv(ENV_VAR, "")

    # Act
    sources = load_sources(arg_file)

    # Assert
    assert [s.url for s in sources] == ["https://github.com/foo/arg.git"]
