from setuptools import setup, find_packages

setup(
    name="gat-plugin-example",
    version="0.1.0",
    author="Micah Webb",
    author_email="micah.webb@nlr.gov",
    description="An example external plotting plugin for GAT.",
    py_modules=["plot"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.8',
    install_requires=[
        "matplotlib"
    ],
    entry_points={
        'gat_ext': [
            'gat_plugin_example = plot',
        ],
    },
)
