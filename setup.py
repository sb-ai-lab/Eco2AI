from setuptools import setup

with open("README.md", "r") as f:
    long_description = f.read()

DEPENDENCIES = [
    "APScheduler",
    "pynvml>=5.6.2",
    "psutil",
    "py-cpuinfo",
]

setup(
    name = 'eco2ai',
    version = '0.2.2',
    author=["Vladimir Lazarev", 'Nikita Zakharenko', 'Semyon Budyonny', 'Leonid Zhukov'],
    description = long_description,
    packages = ['eco2ai'],
    install_requires=DEPENDENCIES,
    package_data={
        "eco2ai": [
            "data/cpu_names.csv",
            "data/config.txt",
            "data/carbon_index.csv"
        ]
    },
    include_package_data=True
)