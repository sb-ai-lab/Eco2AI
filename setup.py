from setuptools import find_packages, setup

__version__ = "0.3.13"

with open("README.md", "r") as f:
    long_description = f.read()

DEPENDENCIES = [
    "APScheduler<4",
    "psutil>=5.9.1,<8",
    "py-cpuinfo<11",
    "pandas>=1.2.1,<=1.3.5; python_version>='3.7.1' and python_version<'3.8'",
    "pandas>=1.4.0,<4; python_version>='3.8'",
    "numpy>=1.16.5,<3",
    "requests<3",
    "tzlocal<6",
    "tornado<7",
]

setup(
    name = 'eco2ai',
    author=["Vladimir Lazarev", 'Nikita Zakharenko', 'Alexey Korovin', 'Semyon Budyonny', 'Leonid Zhukov'],
    description = long_description,
    packages = find_packages(include=["eco2ai", "eco2ai.*"]),
    install_requires=DEPENDENCIES,
    package_data={
        "eco2ai": [
            "data/cpu_names.csv",
            "data/config.txt",
            "data/carbon_index.csv",
            "data/SOURCES.md"
        ]
    },
    include_package_data=True,
    version=__version__,
    entry_points={
        "console_scripts": [
            "eco2ai=eco2ai.configure:main",
        ],
    },
)
