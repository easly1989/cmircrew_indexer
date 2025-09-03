#!/usr/bin/env python3
"""Setup script for MirCrew Indexer"""
from setuptools import setup, find_packages

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setup(
    name="mircrew-indexer",
    version="1.0.0",
    description="Torznab-compatible indexer for MirCrew releases",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=requirements,
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "mircrew-indexer=mircrew.core.indexer:main",
            "mircrew-api=mircrew.api.server:main",
        ]
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Utilities",
    ],
    keywords="mircrew indexer torznab magnet torrent",
    author="MirCrew Community",
    url="https://github.com/mircrew/mircrew-indexer",
    project_urls={
        "Bug Reports": "https://github.com/mircrew/mircrew-indexer/issues",
        "Source": "https://github.com/mircrew/mircrew-indexer",
    },
)