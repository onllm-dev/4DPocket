"""Custom hatch build hook to conditionally bundle frontend static files."""

import os

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    PLUGIN_NAME = "custom"

    def initialize(self, version, build_data):
        frontend_dist = os.path.join(self.root, "frontend", "dist")
        if os.path.isdir(frontend_dist):
            build_data["force_include"][frontend_dist] = "fourdpocket/static"
