from setuptools import setup, find_packages

setup(
    name="grid_game_core",
    version="0.1.0",
    description="Core module for grid-based guessing games",
    author="Nils Brinkmann",
    author_email="grid_game_core@nilsbrinkmann.com",
    packages=find_packages(),
    install_requires=[
        "Django>=4.0",
        "django-prometheus",
    ],
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
) 