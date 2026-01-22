"""
GlassBox Discovery Engine

An explainable, logic-first client discovery engine for freelancers.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="glassbox-engine",
    version="0.1.0",
    author="GlassBox Contributors",
    description="An explainable, logic-first client discovery engine",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/glassbox-engine",
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Office/Business",
    ],
    python_requires=">=3.10",
    install_requires=[
        # No external dependencies - stdlib only
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "glassbox=glassbox.cli.main:main",
        ],
    },
)
