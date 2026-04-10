"""Setup script for OLED Dashboard."""

from setuptools import setup, find_packages

setup(
    name="oled-dashboard",
    version="1.0.0",
    description="Web-configurable OLED display manager for Raspberry Pi",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Adithya",
    license="MIT",
    url="https://github.com/Cr4zySh4rk/oled-dashboard",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "oled_dashboard": [
            "web/templates/*.html",
            "web/static/css/*.css",
            "web/static/js/*.js",
            "web/static/img/*",
        ],
    },
    python_requires=">=3.7",
    install_requires=[
        "flask>=2.0",
        "Pillow>=9.0",
        "requests>=2.28",
        "adafruit-circuitpython-ssd1306>=2.12",
        "adafruit-blinka>=8.0",
        "luma.oled>=3.8",
        "luma.core>=2.3",
        "RPi.GPIO>=0.7",
    ],
    extras_require={
        "dev": ["pytest", "black", "flake8"],
    },
    entry_points={
        "console_scripts": [
            "oled-dashboard=oled_dashboard.__main__:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Topic :: System :: Hardware",
        "Topic :: System :: Monitoring",
    ],
)
