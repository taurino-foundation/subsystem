# SPDX-License-Identifier: MIT OR Apache-2.0

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

# Dynamically imported Taurino modules.
hiddenimports = [
    "taurino.runtime.core",
]

# Collect Taurino's internal Python modules.
hiddenimports += collect_submodules(
    "taurino.runtime",
    filter=lambda name: not name.endswith(".core"),
)

# Additional native libraries shipped inside Taurino.
binaries = collect_dynamic_libs("taurino")

# Runtime resources, if provided by Taurino.
datas = collect_data_files(
    "taurino",
    excludes=[
        "**/__pycache__/**",
        "**/*.pyi",
        "**/tests/**",
    ],
)
