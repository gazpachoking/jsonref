import setuptools

from jsonref import __version__


class PyTest(setuptools.Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        import subprocess
        errno = subprocess.call(['py.test', 'tests.py'])
        raise SystemExit(errno)


with open("README.rst") as readme:
    long_description = readme.read()


classifiers = [
    "Development Status :: 1 - Planning",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.3",
    "Programming Language :: Python :: 3.4",
    "Programming Language :: Python :: 3.5",
    "Programming Language :: Python :: 3.6",
    "Programming Language :: Python :: 3.7",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: Implementation :: CPython",
    "Programming Language :: Python :: Implementation :: PyPy",
]


setuptools.setup(
    name="jsonref",
    version=__version__,
    py_modules=["jsonref", "proxytypes"],
    author="Chase Sterling",
    author_email="chase.sterling@gmail.com",
    classifiers=classifiers,
    description="An implementation of JSON Reference for Python",
    license="MIT",
    long_description=long_description,
    url="https://github.com/gazpachoking/jsonref",
    tests_require=["pytest"],
    cmdclass={
        'test': PyTest,
    },
)
