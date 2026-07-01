"""Direct tests for the (mostly stubbed) Figma URL extractor."""

import pytest

from processors.enhanced_figma_processor import EnhancedFigmaProcessor


class TestExtractFileKeyFromUrl:
    @pytest.fixture
    def processor(self, monkeypatch):
        # We never touch the network; provide a fake token so __init__ succeeds.
        monkeypatch.setenv("FIGMA_API_TOKEN", "fake-token")
        return EnhancedFigmaProcessor(api_token="fake-token")

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://www.figma.com/design/abc123/Foo", "abc123"),
            ("https://www.figma.com/file/ABCdef/Title", "ABCdef"),
            ("https://figma.com/proto/xyz789/Quick", "xyz789"),
        ],
    )
    def test_extracts_key_for_known_routes(self, processor, url, expected):
        assert processor.extract_file_key_from_url(url) == expected

    def test_returns_none_for_unknown_route(self, processor):
        assert processor.extract_file_key_from_url("https://www.figma.com/community/foo") is None

    def test_returns_none_for_unparseable_url(self, processor):
        assert processor.extract_file_key_from_url("not-a-url") is None

    def test_returns_none_when_key_segment_missing(self, processor):
        assert processor.extract_file_key_from_url("https://www.figma.com/design/") is None
