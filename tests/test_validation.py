"""Direct invocation of the validation helpers."""

from validation import (
    MAX_FIGMA_URL_LENGTH,
    MAX_FRAMEWORK_LENGTH,
    MAX_PAT_TOKEN_LENGTH,
    clamp_zip_path,
    is_safe_under,
    validate_figma_url,
)


class TestValidateFigmaUrl:
    def test_accepts_https_www_figma(self):
        key = validate_figma_url(
            "https://www.figma.com/design/ABCxyz1234567890abcdef/Foo"
        )
        assert key == "ABCxyz1234567890abcdef"

    def test_accepts_file_route(self):
        key = validate_figma_url(
            "https://www.figma.com/file/ABCxyz1234567890abcdef/Title"
        )
        assert key == "ABCxyz1234567890abcdef"

    def test_accepts_proto_route(self):
        key = validate_figma_url(
            "https://www.figma.com/proto/ABCxyz1234567890abcdef/Quick"
        )
        assert key == "ABCxyz1234567890abcdef"

    def test_accepts_bare_host(self):
        key = validate_figma_url("https://figma.com/design/ABCxyz1234567890abcdef/Foo")
        assert key == "ABCxyz1234567890abcdef"

    def test_rejects_attacker_host(self):
        assert validate_figma_url("https://attacker.invalid/design/AAA/file") is None

    def test_rejects_javascript_scheme(self):
        assert validate_figma_url("javascript:alert(1)") is None

    def test_rejects_too_long(self):
        url = "https://www.figma.com/design/" + ("A" * (MAX_FIGMA_URL_LENGTH - 32)) + "/Foo"
        assert validate_figma_url(url) is None

    def test_rejects_short_key(self):
        assert validate_figma_url("https://www.figma.com/design/short/Foo") is None

    def test_rejects_special_chars_in_key(self):
        assert (
            validate_figma_url("https://www.figma.com/design/ABC../etc/Foo") is None
        )


class TestPathClamping:
    def test_accepts_file_under_root(self, tmp_path):
        allowed = tmp_path
        inner = allowed / "foo.zip"
        inner.write_bytes(b"hello")
        assert is_safe_under(inner, allowed)

    def test_rejects_traversal(self, tmp_path):
        outside = tmp_path.parent / "etc" / "passwd"
        outside.parent.mkdir(parents=True, exist_ok=True)
        outside.write_text("secret")
        allowed = tmp_path / "real"
        allowed.mkdir()
        assert not is_safe_under(outside, allowed)

    def test_clamp_returns_none_for_escape(self, tmp_path):
        result = clamp_zip_path(str(tmp_path.parent / "etc" / "passwd"), tmp_path)
        assert result is None

    def test_clamp_returns_path_inside_root(self, tmp_path):
        inner = tmp_path / "project.zip"
        inner.write_bytes(b"ok")
        result = clamp_zip_path(str(inner), tmp_path)
        assert result == inner.resolve()


def test_length_limits_match_documented_values():
    # The constants should not silently change without unit-test coverage.
    assert MAX_FIGMA_URL_LENGTH <= 2048
    assert MAX_FRAMEWORK_LENGTH >= 256
    assert MAX_PAT_TOKEN_LENGTH >= 256
