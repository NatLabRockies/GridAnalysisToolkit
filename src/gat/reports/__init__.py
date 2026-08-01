"""
GAT Reports Package

This package contains various report modules for generating visualizations and
analyzing simulation results.

Each report module should implement a register_commands(cli_group) function
to register its CLI commands.
"""

# Import all report modules to ensure they're available for CLI registration
from . import system_comparison
from . import scenario_single
#from . import standard_multi
#from . import generation_report