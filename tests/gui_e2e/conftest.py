#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

"""some fixtures related to e2e tests and playwright"""
import logging
import re
from collections.abc import Iterator
from typing import Any

import pytest
from playwright.sync_api import Browser, BrowserContext, expect, Page
from playwright.sync_api import TimeoutError as PWTimeoutError

from tests.testlib.host_details import HostDetails
from tests.testlib.playwright.helpers import CmkCredentials
from tests.testlib.playwright.plugin import (
    manage_new_browser_context,
    manage_new_page_from_browser_context,
)
from tests.testlib.playwright.pom.dashboard import Dashboard, DashboardMobile
from tests.testlib.playwright.pom.login import LoginPage
from tests.testlib.playwright.pom.setup.hosts import AddHost, SetupHost
from tests.testlib.site import ADMIN_USER, get_site_factory, Site

logger = logging.getLogger(__name__)


@pytest.fixture(name="test_site", scope="session")
def fixture_test_site() -> Iterator[Site]:
    """Return the Checkmk site object."""
    yield from get_site_factory(prefix="gui_e2e_").get_test_site()


@pytest.fixture(name="credentials", scope="session")
def fixture_credentials(test_site: Site) -> CmkCredentials:
    """Return admin user credentials of the Checkmk site."""
    return CmkCredentials(username=ADMIN_USER, password=test_site.admin_password)


def _log_in(
    context: BrowserContext,
    credentials: CmkCredentials,
    request: pytest.FixtureRequest,
    test_site: Site,
) -> None:
    video_name = f"login_for_{request.node.name.replace('.py', '')}"
    with manage_new_page_from_browser_context(context, request, video_name) as page:
        login_page = LoginPage(page, site_url=test_site.internal_url)
        login_page.login(credentials)


@pytest.fixture(name="_logged_in_page", scope="module")
def _logged_in(
    test_site: Site,
    credentials: CmkCredentials,
    _context: BrowserContext,
    request: pytest.FixtureRequest,
) -> None:
    _log_in(_context, credentials, request, test_site)


@pytest.fixture(name="_logged_in_page_mobile", scope="module")
def _logged_in_mobile(
    test_site: Site,
    credentials: CmkCredentials,
    _context_mobile: BrowserContext,
    request: pytest.FixtureRequest,
) -> None:
    _log_in(_context_mobile, credentials, request, test_site)


@pytest.fixture(name="dashboard_page")
def fixture_dashboard_page(
    page: Page, _logged_in_page: None, test_site: Site, credentials: CmkCredentials
) -> Dashboard:
    """Entrypoint to test browser GUI. Navigates to 'Main Dashboard'."""
    _obj = _navigate_to_dashboard(page, test_site.internal_url, credentials)
    if isinstance(_obj, Dashboard):
        return _obj  # handle type-hinting
    raise TypeError("Expected Dashboard PoM corresponding to browser GUI!")


@pytest.fixture(name="dashboard_page_mobile")
def fixture_dashboard_page_mobile(
    page_mobile: Page, _logged_in_page_mobile: None, test_site: Site, credentials: CmkCredentials
) -> DashboardMobile:
    """Entrypoint to test mobile GUI. Navigates to 'Mobile Dashboard'"""
    _obj = _navigate_to_dashboard(page_mobile, test_site.internal_url_mobile, credentials)
    if isinstance(_obj, DashboardMobile):
        return _obj  # handle type-hinting
    raise TypeError("Expected Dashboard PoM corresponding to mobile GUI!")


def _navigate_to_dashboard(
    page: Page, url: str, credentials: CmkCredentials
) -> Dashboard | DashboardMobile:
    """Navigate to dashboard page.

    Performs a login to Checkmk site, if necessary.
    """
    dashboard_type: type[Dashboard | DashboardMobile] = (
        DashboardMobile if "mobile.py" in url else Dashboard
    )
    page.goto(url, wait_until="load")
    try:
        return dashboard_type(page, navigate_to_page=False)
    except (PWTimeoutError, AssertionError) as _:
        # logged out
        expect(page, f"Expected login page, found: {page.url}!").to_have_url(re.compile("login.py"))
        LoginPage(page, url, navigate_to_page=False).login(credentials)
        return dashboard_type(page, navigate_to_page=False)


@pytest.fixture(name="new_browser_context_and_page")
def fixture_new_browser_context_and_page(
    _browser: Browser,
    context_launch_kwargs: dict[str, Any],
    request: pytest.FixtureRequest,
) -> Iterator[tuple[BrowserContext, Page]]:
    """Create a new browser context from the existing browser session and return a new page.

    Usually, a browser context is setup once for every test-module.
    This context is shared among all the pages created by the tests present within the module.
    For example, cookies are shared among all the test cases.

    In the case a fresh browser context is required, use this fixture.

    NOTE: fresh context requires a login to the Checkmk site. Refer to `LoginPage` for details.
    """
    with manage_new_browser_context(_browser, context_launch_kwargs) as context:
        with manage_new_page_from_browser_context(context, request) as page:
            yield context, page


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-rules",
        action="store_true",
        default=False,
        help="Store updated rule output as static references: rules already stored as reference"
        "are updated and new ones are added.",
    )


@pytest.fixture(name="created_host")
def fixture_host(
    dashboard_page: Dashboard, request: pytest.FixtureRequest
) -> Iterator[HostDetails]:
    """Create a host and delete it after the test.

    This fixture uses indirect pytest parametrization to define host details.
    """
    host_details = request.param
    add_host_page = AddHost(dashboard_page.page)
    add_host_page.create_host(host_details)
    yield host_details
    setup_host_page = SetupHost(dashboard_page.page)
    setup_host_page.select_hosts([host_details.name])
    setup_host_page.delete_selected_hosts()
    setup_host_page.activate_changes()
