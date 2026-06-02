#!/usr/bin/env python3
"""
Setup script for Cirq-RAG-Code-Assistant.

This script provides backward compatibility for pip installations
while the main configuration is in pyproject.toml.
"""

from setuptools import setup

# Read the README file for long description
try:
    with open("README.md", "r", encoding="utf-8") as fh:
        long_description = fh.read()
except FileNotFoundError:
    long_description = "A research-grade system for generating and explaining Cirq quantum computing code"

# Read requirements from requirements.txt
try:
    with open("requirements.txt", "r", encoding="utf-8") as fh:
        raw_lines = [l.strip() for l in fh.readlines() if l.strip() and not l.strip().startswith("#")]
        requirements = []
        for line in raw_lines:
            if line.startswith("-r "):
                ref = line.split(None, 1)[1]
                try:
                    with open(ref, "r", encoding="utf-8") as reffh:
                        requirements.extend(
                            [l.strip() for l in reffh.readlines() if l.strip() and not l.strip().startswith("#")]
                        )
                except FileNotFoundError:
                    # ignore missing referenced file; keep the original line
                    requirements.append(line)
            else:
                requirements.append(line)
except FileNotFoundError:
    requirements = []

setup(
    name="cirq-rag-code-assistant",
    version="0.1.0",
    author="Umer Farooq, Hussain Waseem Syed, Muhammad Irtaza Khan",
    author_email="umerfarooqcs0891@gmail.com",
    description="A research-grade system for generating and explaining Cirq quantum computing code using RAG and multi-agent architecture with PyTorch CUDA optimization",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/umerfarooq/cirq-rag-code-assistant",
    project_urls={
        "Bug Reports": "https://github.com/umerfarooq/cirq-rag-code-assistant/issues",
        "Source": "https://github.com/umerfarooq/cirq-rag-code-assistant",
        "Documentation": "https://cirq-rag-code-assistant.readthedocs.io",
    },
    packages=["cirq_rag_code_assistant"],
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Education",
        "Topic :: Scientific/Engineering :: Physics",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Code Generators",
        "License :: Other/Proprietary License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Environment :: Console",
        "Environment :: Web Environment",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
            "black>=23.9.0",
            "isort>=5.12.0",
            "flake8>=6.1.0",
            "mypy>=1.6.0",
            "pre-commit>=3.5.0",
            "jupyter>=1.0.0",
            "ipython>=8.17.0",
        ],
        "docs": [
            "sphinx>=7.2.0",
            "sphinx-rtd-theme>=1.3.0",
            "mkdocs>=1.5.0",
            "mkdocs-material>=9.4.0",
        ],
        "gpu": [
            "faiss-gpu>=1.7.4",
            "cupy>=12.0.0",
        ],
        "quantum": [
            "qiskit>=0.45.0",
            "pennylane>=0.34.0",
            "qutip>=4.7.0",
        ],
        "qcanvas": [
            "qiskit>=0.45.0",
            "pennylane>=0.34.0",
            "qutip>=4.7.0",
            "fastapi>=0.104.0",
            "websockets>=11.0.3",
        ],
    },
    entry_points={
        "console_scripts": [
            "cirq-rag=cirq_rag_code_assistant.cli.main:main",
            "cirq-rag-server=cirq_rag_code_assistant.api.server:main",
        ],
        "gui_scripts": [
            "cirq-rag-gui=cirq_rag_code_assistant.gui.main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "cirq_rag_code_assistant": [
            "data/*",
            "templates/*",
            "static/*",
            "*.yaml",
            "*.yml",
            "*.json",
        ],
    },
    zip_safe=False,
    keywords=[
        "quantum computing",
        "cirq",
        "rag",
        "multi-agent",
        "code generation",
        "quantum algorithms",
        "machine learning",
        "natural language processing",
    ],
)
