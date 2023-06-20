from setuptools import find_packages, setup

with open("README.md", "r") as readme_file:
    readme = readme_file.read()


with open("requirements.txt", "r") as fh:
    requirements = fh.readlines()


setup(
    name="indy-rewards",
    version="0.1.0",
    author="Indigo Labs",
    description="CLI application for distributing INDY rewards",
    long_description=readme,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    install_requires=[
        req for req in requirements if req.strip() and not req.strip().startswith("#")
    ],
    python_requires=">=3.10",
    classifiers=[
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    entry_points={
        "console_scripts": [
            "indy-rewards=indy_rewards.cli:rewards",
        ],
    },
)
