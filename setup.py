#!/usr/bin/env python3
"""Setup script for MirCrew Indexer"""
from setuptools import setup, find_packages

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setup(
    # Metadata is now managed in pyproject.toml
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=requirements,
    )