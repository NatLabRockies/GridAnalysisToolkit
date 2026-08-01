# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os
import sys
sys.path.insert(0, os.path.abspath('../../src'))

# Import the version
try:
    from gat._version import version
except ImportError:
    # If not installed, setuptools_scm can get the version directly
    from setuptools_scm import get_version
    version = get_version(root='../..', relative_to=__file__)

# Use in Sphinx configuration
release = version


project = 'Grid Analysis Toolkit'
copyright = '2026, Alliance for Energy Innovation, LLC'
author = 'Micah Webb'

import os.path as op

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'myst_parser',
    "sphinx_copybutton",
    "sphinx.ext.autodoc",
    "sphinx_tabs.tabs",
    "sphinx.ext.autosummary",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.coverage",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinxcontrib.mermaid",
    "sphinx_gallery.gen_gallery",
    "sphinx_click.ext"
]

templates_path = ['_templates']

# Make sure the target is unique
autosectionlabel_prefix_document = True

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# autosummary_generate = True  # Turn on sphinx.ext.autosummary



html_theme = "sphinx_book_theme"
html_static_path = ["_static"]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

html_theme_options = {
    "repository_url": "https://github.com/NatLabRockies/GridAnalysisToolkit",
    "path_to_docs": "docs/source/",
    "show_toc_level": 3,
    "use_source_button": True,
    "use_edit_page_button": True,
}

myst_enable_extensions = [
    "amsmath",
    "attrs_inline",
    "attrs_block",
    "colon_fence",
    "deflist",
    "dollarmath",
    "fieldlist",
    "html_admonition",
    "html_image",
    "colon_fence",
    "replacements",
    "smartquotes",
    "strikethrough",
    "substitution",
    "tasklist",
]

# Gallery Configuration
sphinx_gallery_conf = {
    # Path to example scripts
    'examples_dirs': ['../gat_examples'],

    # Path to save examples
    'gallery_dirs': ['gat_plot_examples'],

    'filename_pattern': r'/*.py',

    'backreferences_dir': op.join('modules','generated'),

    # Examples are alpha-sorted by filename; numeric prefixes (01_, 02_, …)
    # establish the gallery order without an explicit subsection_order.
}

# -- Options for autodoc ----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#configuration

# Automatically extract typehints when specified and place them in
# descriptions of the relevant function/method.
autodoc_typehints = "description"

# Don't show class signature with the class' name.
# autodoc_class_signature = "separated"
suppress_warnings = ["myst.header"]