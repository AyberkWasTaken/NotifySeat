from setuptools import setup, find_packages

setup(
    name="notifyseat",
    version="1.0.0",
    description="Local-First Transport Seat & Cancellation Notifier",
    author="Ayberk",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "notifyseat.web": [
            "templates/*.html",
            "static/css/*.css",
            "static/js/*.js",
        ],
    },
    install_requires=[
        "requests>=2.28.0",
        "rich>=13.0.0",
    ],
    entry_points={
        "console_scripts": [
            "notifyseat=notifyseat.cli.app:main",
        ],
    },
    python_requires=">=3.8",
)
