#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

from cmk.gui.i18n import _
from cmk.gui.permissions import PermissionSection

permission_section_sidebar_snapins = PermissionSection(
    name="sidesnap",
    title=_("Sidebar elements"),
    do_sort=True,
)
