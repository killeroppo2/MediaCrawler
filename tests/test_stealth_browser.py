# -*- coding: utf-8 -*-
"""
Unit tests for CloakBrowser stealth browser integration.

Tests cover:
- Config defaults for stealth browser settings
- AbstractCrawler.launch_browser_stealth() method
- Platform crawler stealth branching logic
- Edge cases

NOTE on patch targets:
    Patches target 'cloakbrowser.launch_context_async' and
    'cloakbrowser.launch_persistent_context_async' at module level because the
    production code in base/base_crawler.py uses a local import inside the
    function body:

        async def launch_browser_stealth(...):
            from cloakbrowser import launch_context_async, launch_persistent_context_async

    With a local import like this, the names are looked up from the cloakbrowser
    package each time the function runs, so we must patch the source module
    ('cloakbrowser.launch_context_async') rather than the importer
    ('base.base_crawler.launch_context_async'). If the import style is ever
    changed to a top-level import, these patches must be updated to target
    'base.base_crawler.launch_context_async' instead.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from playwright.async_api import BrowserContext, BrowserType, Playwright

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import config
from base.base_crawler import AbstractCrawler


class _TestHalt(Exception):
    """Sentinel exception used to halt crawler execution at a known point.

    Replaces StopAsyncIteration (which has special async iterator semantics)
    so that tests can catch exactly this exception without swallowing unrelated
    errors via a bare except clause.
    """
    pass


# Concrete subclass of AbstractCrawler for testing
class ConcreteCrawler(AbstractCrawler):
    """Concrete implementation of AbstractCrawler for testing purposes."""

    async def start(self):
        pass

    async def search(self):
        pass

    async def launch_browser(
        self,
        chromium: BrowserType,
        playwright_proxy: Optional[Dict],
        user_agent: Optional[str],
        headless: bool = True,
    ) -> BrowserContext:
        pass


@pytest.fixture
def async_playwright_mock():
    """Pre-configured async_playwright context manager mock.

    Returns a tuple of (context_manager_mock, playwright_instance_mock) so
    tests can patch 'media_platform.xhs.core.async_playwright' (or equivalent)
    with the context manager and access the playwright instance for further
    stubbing.
    """
    mock_playwright = AsyncMock()
    mock_cm = MagicMock()
    mock_cm.return_value.__aenter__ = AsyncMock(return_value=mock_playwright)
    mock_cm.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_cm, mock_playwright


class TestStealthBrowserConfig:
    """Test config/base_config.py stealth browser settings."""

    def test_enable_stealth_browser_default(self):
        """ENABLE_STEALTH_BROWSER should default to False."""
        assert config.ENABLE_STEALTH_BROWSER is False

    def test_stealth_humanize_default(self):
        """STEALTH_HUMANIZE should default to True."""
        assert config.STEALTH_HUMANIZE is True

    def test_stealth_human_preset_default(self):
        """STEALTH_HUMAN_PRESET should default to 'default'."""
        assert config.STEALTH_HUMAN_PRESET == "default"


class TestLaunchBrowserStealth:
    """Test AbstractCrawler.launch_browser_stealth() method."""

    @pytest.mark.asyncio
    @patch('config.SAVE_LOGIN_STATE', True)
    @patch('config.PLATFORM', 'xhs')
    @patch('cloakbrowser.launch_persistent_context_async', new_callable=AsyncMock)
    @patch('cloakbrowser.launch_context_async', new_callable=AsyncMock)
    async def test_persistent_context_when_save_login_state_true(
        self, mock_launch_context, mock_launch_persistent
    ):
        """When SAVE_LOGIN_STATE=True, launch_persistent_context_async should be called."""
        mock_browser_context = AsyncMock()
        mock_launch_persistent.return_value = mock_browser_context

        crawler = ConcreteCrawler()
        result = await crawler.launch_browser_stealth(
            playwright_proxy=None,
            user_agent=None,
            headless=True,
        )

        mock_launch_persistent.assert_called_once()
        call_kwargs = mock_launch_persistent.call_args[1]
        assert "xhs" in call_kwargs["user_data_dir"]
        assert call_kwargs["headless"] is True
        assert call_kwargs["proxy"] is None
        assert call_kwargs["user_agent"] is None
        assert call_kwargs["viewport"] == {"width": 1920, "height": 1080}
        assert call_kwargs["humanize"] == config.STEALTH_HUMANIZE
        assert call_kwargs["human_preset"] == config.STEALTH_HUMAN_PRESET
        mock_launch_context.assert_not_called()
        assert result == mock_browser_context

    @pytest.mark.asyncio
    @patch('config.SAVE_LOGIN_STATE', False)
    @patch('cloakbrowser.launch_context_async', new_callable=AsyncMock)
    @patch('cloakbrowser.launch_persistent_context_async', new_callable=AsyncMock)
    async def test_context_when_save_login_state_false(
        self, mock_launch_persistent, mock_launch_context
    ):
        """When SAVE_LOGIN_STATE=False, launch_context_async should be called."""
        mock_browser_context = AsyncMock()
        mock_launch_context.return_value = mock_browser_context

        crawler = ConcreteCrawler()
        result = await crawler.launch_browser_stealth(
            playwright_proxy=None,
            user_agent=None,
            headless=True,
        )

        mock_launch_context.assert_called_once()
        call_kwargs = mock_launch_context.call_args[1]
        assert call_kwargs["headless"] is True
        assert call_kwargs["proxy"] is None
        assert call_kwargs["user_agent"] is None
        assert call_kwargs["viewport"] == {"width": 1920, "height": 1080}
        assert call_kwargs["humanize"] == config.STEALTH_HUMANIZE
        assert call_kwargs["human_preset"] == config.STEALTH_HUMAN_PRESET
        mock_launch_persistent.assert_not_called()
        assert result == mock_browser_context

    @pytest.mark.asyncio
    @patch('config.SAVE_LOGIN_STATE', False)
    @patch('cloakbrowser.launch_context_async', new_callable=AsyncMock)
    @patch('cloakbrowser.launch_persistent_context_async', new_callable=AsyncMock)
    async def test_proxy_passed_correctly(self, mock_launch_persistent, mock_launch_context):
        """Proxy dict should be forwarded to the CloakBrowser function."""
        proxy = {"server": "http://proxy:8080"}

        crawler = ConcreteCrawler()
        await crawler.launch_browser_stealth(
            playwright_proxy=proxy,
            user_agent=None,
            headless=True,
        )

        call_kwargs = mock_launch_context.call_args[1]
        assert call_kwargs["proxy"] == {"server": "http://proxy:8080"}

    @pytest.mark.asyncio
    @patch('config.SAVE_LOGIN_STATE', False)
    @patch('cloakbrowser.launch_context_async', new_callable=AsyncMock)
    @patch('cloakbrowser.launch_persistent_context_async', new_callable=AsyncMock)
    async def test_user_agent_passed_correctly(self, mock_launch_persistent, mock_launch_context):
        """User agent string should be forwarded to the CloakBrowser function."""
        user_agent = "Mozilla/5.0 Custom Agent"

        crawler = ConcreteCrawler()
        await crawler.launch_browser_stealth(
            playwright_proxy=None,
            user_agent=user_agent,
            headless=True,
        )

        call_kwargs = mock_launch_context.call_args[1]
        assert call_kwargs["user_agent"] == "Mozilla/5.0 Custom Agent"

    @pytest.mark.asyncio
    @patch('config.SAVE_LOGIN_STATE', False)
    @patch('cloakbrowser.launch_context_async', new_callable=AsyncMock)
    @patch('cloakbrowser.launch_persistent_context_async', new_callable=AsyncMock)
    async def test_proxy_none(self, mock_launch_persistent, mock_launch_context):
        """Proxy=None should be forwarded as None."""
        crawler = ConcreteCrawler()
        await crawler.launch_browser_stealth(
            playwright_proxy=None,
            user_agent=None,
            headless=True,
        )

        call_kwargs = mock_launch_context.call_args[1]
        assert call_kwargs["proxy"] is None

    @pytest.mark.asyncio
    @patch('config.SAVE_LOGIN_STATE', False)
    @patch('cloakbrowser.launch_context_async', new_callable=AsyncMock)
    @patch('cloakbrowser.launch_persistent_context_async', new_callable=AsyncMock)
    async def test_user_agent_none(self, mock_launch_persistent, mock_launch_context):
        """user_agent=None should be forwarded as None."""
        crawler = ConcreteCrawler()
        await crawler.launch_browser_stealth(
            playwright_proxy=None,
            user_agent=None,
            headless=True,
        )

        call_kwargs = mock_launch_context.call_args[1]
        assert call_kwargs["user_agent"] is None

    @pytest.mark.asyncio
    @patch('config.SAVE_LOGIN_STATE', False)
    @patch('cloakbrowser.launch_context_async', new_callable=AsyncMock)
    @patch('cloakbrowser.launch_persistent_context_async', new_callable=AsyncMock)
    async def test_headless_true(self, mock_launch_persistent, mock_launch_context):
        """headless=True should be forwarded correctly."""
        crawler = ConcreteCrawler()
        await crawler.launch_browser_stealth(
            playwright_proxy=None,
            user_agent=None,
            headless=True,
        )

        call_kwargs = mock_launch_context.call_args[1]
        assert call_kwargs["headless"] is True

    @pytest.mark.asyncio
    @patch('config.SAVE_LOGIN_STATE', False)
    @patch('cloakbrowser.launch_context_async', new_callable=AsyncMock)
    @patch('cloakbrowser.launch_persistent_context_async', new_callable=AsyncMock)
    async def test_headless_false(self, mock_launch_persistent, mock_launch_context):
        """headless=False should be forwarded correctly."""
        crawler = ConcreteCrawler()
        await crawler.launch_browser_stealth(
            playwright_proxy=None,
            user_agent=None,
            headless=False,
        )

        call_kwargs = mock_launch_context.call_args[1]
        assert call_kwargs["headless"] is False

    @pytest.mark.asyncio
    @patch('config.STEALTH_HUMANIZE', False)
    @patch('config.STEALTH_HUMAN_PRESET', 'careful')
    @patch('config.SAVE_LOGIN_STATE', False)
    @patch('cloakbrowser.launch_context_async', new_callable=AsyncMock)
    @patch('cloakbrowser.launch_persistent_context_async', new_callable=AsyncMock)
    async def test_custom_humanize_settings(self, mock_launch_persistent, mock_launch_context):
        """Custom STEALTH_HUMANIZE and STEALTH_HUMAN_PRESET values should be passed."""
        crawler = ConcreteCrawler()
        await crawler.launch_browser_stealth(
            playwright_proxy=None,
            user_agent=None,
            headless=True,
        )

        call_kwargs = mock_launch_context.call_args[1]
        assert call_kwargs["humanize"] is False
        assert call_kwargs["human_preset"] == "careful"

    @pytest.mark.asyncio
    @patch('config.SAVE_LOGIN_STATE', False)
    @patch('cloakbrowser.launch_context_async', new_callable=AsyncMock)
    @patch('cloakbrowser.launch_persistent_context_async', new_callable=AsyncMock)
    async def test_returns_browser_context(self, mock_launch_persistent, mock_launch_context):
        """The method should return whatever the mocked CloakBrowser function returns."""
        expected_context = AsyncMock(spec=BrowserContext)
        mock_launch_context.return_value = expected_context

        crawler = ConcreteCrawler()
        result = await crawler.launch_browser_stealth(
            playwright_proxy=None,
            user_agent=None,
            headless=True,
        )

        assert result is expected_context


class TestPlatformStealthBranch:
    """Test stealth branching logic in platform crawlers.

    These tests verify that the config-driven dispatch in each platform's
    start() method calls the correct browser launch mechanism. A custom
    _TestHalt exception is used to stop execution immediately after the
    browser context is assigned, preventing downstream code (login, client
    creation, crawling) from running. Only _TestHalt is caught, so any
    unexpected exception will correctly fail the test.
    """

    @pytest.mark.asyncio
    @patch('config.ENABLE_STEALTH_BROWSER', True)
    @patch('config.ENABLE_IP_PROXY', False)
    @patch('config.HEADLESS', True)
    async def test_xhs_stealth_branch(self):
        """XiaoHongShuCrawler should call launch_browser_stealth when ENABLE_STEALTH_BROWSER=True."""
        from media_platform.xhs.core import XiaoHongShuCrawler

        crawler = XiaoHongShuCrawler()
        mock_browser_context = AsyncMock()

        with patch.object(
            crawler, 'launch_browser_stealth', new_callable=AsyncMock, return_value=mock_browser_context
        ) as mock_stealth:
            # Halt execution at new_page() - the first call after browser context assignment
            mock_browser_context.new_page = AsyncMock(side_effect=_TestHalt("halt after stealth launch"))
            try:
                await crawler.start()
            except _TestHalt:
                pass

            mock_stealth.assert_called_once_with(
                None,
                crawler.user_agent,
                headless=True,
            )

    @pytest.mark.asyncio
    @patch('config.ENABLE_STEALTH_BROWSER', True)
    @patch('config.ENABLE_IP_PROXY', False)
    @patch('config.HEADLESS', True)
    async def test_douyin_stealth_branch(self):
        """DouYinCrawler should call launch_browser_stealth when ENABLE_STEALTH_BROWSER=True."""
        from media_platform.douyin.core import DouYinCrawler

        crawler = DouYinCrawler()
        mock_browser_context = AsyncMock()

        with patch.object(
            crawler, 'launch_browser_stealth', new_callable=AsyncMock, return_value=mock_browser_context
        ) as mock_stealth:
            # Halt execution at new_page() - the first call after browser context assignment
            mock_browser_context.new_page = AsyncMock(side_effect=_TestHalt("halt after stealth launch"))
            try:
                await crawler.start()
            except _TestHalt:
                pass

            mock_stealth.assert_called_once_with(
                None,
                None,
                headless=True,
            )

    @pytest.mark.asyncio
    @patch('config.ENABLE_STEALTH_BROWSER', True)
    @patch('config.ENABLE_IP_PROXY', False)
    @patch('config.HEADLESS', True)
    async def test_bilibili_stealth_branch(self):
        """BilibiliCrawler should call launch_browser_stealth when ENABLE_STEALTH_BROWSER=True."""
        from media_platform.bilibili.core import BilibiliCrawler

        crawler = BilibiliCrawler()
        mock_browser_context = AsyncMock()

        with patch.object(
            crawler, 'launch_browser_stealth', new_callable=AsyncMock, return_value=mock_browser_context
        ) as mock_stealth:
            # Halt execution at new_page() - the first call after browser context assignment
            mock_browser_context.new_page = AsyncMock(side_effect=_TestHalt("halt after stealth launch"))
            try:
                await crawler.start()
            except _TestHalt:
                pass

            mock_stealth.assert_called_once_with(
                None,
                crawler.user_agent,
                headless=True,
            )

    @pytest.mark.asyncio
    @patch('config.ENABLE_STEALTH_BROWSER', False)
    @patch('config.ENABLE_CDP_MODE', True)
    @patch('config.ENABLE_IP_PROXY', False)
    @patch('config.CDP_HEADLESS', False)
    async def test_xhs_cdp_branch_when_stealth_disabled(self, async_playwright_mock):
        """When stealth disabled and CDP enabled, XHS should use CDP mode."""
        from media_platform.xhs.core import XiaoHongShuCrawler

        crawler = XiaoHongShuCrawler()
        mock_browser_context = AsyncMock()

        with patch.object(
            crawler, 'launch_browser_with_cdp', new_callable=AsyncMock, return_value=mock_browser_context
        ) as mock_cdp:
            mock_cm, _ = async_playwright_mock
            with patch('media_platform.xhs.core.async_playwright', mock_cm):
                # Halt execution at new_page()
                mock_browser_context.new_page = AsyncMock(side_effect=_TestHalt("halt after CDP launch"))
                try:
                    await crawler.start()
                except _TestHalt:
                    pass

                mock_cdp.assert_called_once()

    @pytest.mark.asyncio
    @patch('config.ENABLE_STEALTH_BROWSER', False)
    @patch('config.ENABLE_CDP_MODE', False)
    @patch('config.ENABLE_IP_PROXY', False)
    @patch('config.HEADLESS', True)
    async def test_xhs_standard_branch(self, async_playwright_mock):
        """When both stealth and CDP disabled, XHS should use standard launch_browser."""
        from media_platform.xhs.core import XiaoHongShuCrawler

        crawler = XiaoHongShuCrawler()
        mock_browser_context = AsyncMock()
        mock_browser_context.add_init_script = AsyncMock()

        with patch.object(
            crawler, 'launch_browser', new_callable=AsyncMock, return_value=mock_browser_context
        ) as mock_standard:
            mock_cm, _ = async_playwright_mock
            with patch('media_platform.xhs.core.async_playwright', mock_cm):
                # Halt execution at new_page()
                mock_browser_context.new_page = AsyncMock(side_effect=_TestHalt("halt after standard launch"))
                try:
                    await crawler.start()
                except _TestHalt:
                    pass

                mock_standard.assert_called_once()


class TestEdgeCases:
    """Edge case tests for stealth browser integration."""

    @pytest.mark.asyncio
    @patch('config.SAVE_LOGIN_STATE', True)
    @patch('config.PLATFORM', 'bili')
    @patch('cloakbrowser.launch_persistent_context_async', new_callable=AsyncMock)
    @patch('cloakbrowser.launch_context_async', new_callable=AsyncMock)
    async def test_user_data_dir_contains_platform_bili(
        self, mock_launch_context, mock_launch_persistent
    ):
        """User data dir should contain 'bili' when PLATFORM is 'bili'."""
        crawler = ConcreteCrawler()
        await crawler.launch_browser_stealth(
            playwright_proxy=None,
            user_agent=None,
            headless=True,
        )

        call_kwargs = mock_launch_persistent.call_args[1]
        assert "bili" in call_kwargs["user_data_dir"]

    @pytest.mark.asyncio
    async def test_import_error_when_cloakbrowser_missing(self):
        """launch_browser_stealth should raise ImportError if cloakbrowser is not installed."""
        import importlib
        import builtins

        crawler = ConcreteCrawler()

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == 'cloakbrowser':
                raise ImportError("No module named 'cloakbrowser'")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, '__import__', side_effect=mock_import):
            with pytest.raises(ImportError, match="cloakbrowser"):
                await crawler.launch_browser_stealth(
                    playwright_proxy=None,
                    user_agent=None,
                    headless=True,
                )
