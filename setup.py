from setuptools import setup, find_packages

setup(
    name="utils_example",
    version="0.0.2",
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    author="Example Author",
    author_email="author@example.com",
    description="A small example package",
    url="https://github.com/sampleproject",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
