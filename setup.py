from setuptools import setup, find_packages

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
    version = '0.1.1',
    author="Vladimir Lazarev",
    url = 'https://github.com/sb-ai-lab/Eco2AI.git',
    description = long_description,
    packages = find_packages(),
    install_requires=DEPENDENCIES,
    package_data={
        "eco2ai": [
            "data/cpu_names.csv",
            "data/config.txt"
        ]
    },
    include_package_data=True
)