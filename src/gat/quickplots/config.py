# standard_color_dict moved to gat.colors (dependency-free — it sits on
# the mandatory path for constructing any scenario handler via
# BaseScenario/TechnologyMapping, so it can't require matplotlib).
# Re-exported here under its original name for backward compatibility.
from gat.colors import standard_color_dict  # noqa: F401

volt_line_width = {
    220.0: 0.75,
    230.0: 0.75,
    315.0: 1,
    345.0: 1,
    500.0: 1.25,
    765.0: 1.5,
    735.0: 1.5,
}
