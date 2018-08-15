"""A setuptools based setup module.
See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages, Command
from setuptools.command.build_py import build_py
# To use a consistent encoding
from codecs import open
from os import path, listdir, environ

# make sure we don't need any non-standard libraries like gevent in
# CompileContracts (in case we have set THREADING_BACKEND=gevent)
environ.pop("THREADING_BACKEND", None)

here = path.abspath(path.dirname(__file__))


# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()


class BuildPyCommand(build_py):

    def run(self):
        build_py.run(self)
        self.run_command('compile_contracts')


class CompileContracts(Command):
    description = 'Compile contracts to json'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        from populus import Project
        from populus.api.compile_contracts import compile_project
        project = Project()
        compile_project(project, False)


def list_files(dir_path):
    base_dir = path.join(here, dir_path)
    return [path.join(here, dir_path, f) for f in listdir(base_dir) if path.isfile(path.join(here, dir_path, f))]


setup(
    name='trustlines-contracts',

    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html

    setup_requires=["setuptools_scm"],
    use_scm_version=True,

    description='Smart Contracts for Trustlines-Network',
    long_description=long_description,

    # The project's main homepage.
    url='https://github.com/trustlines-network/contracts',

    # Author details
    author='Trustlines-Network',
    author_email='',

    # Choose your license
    license='MIT',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 2 - Pre-Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: MIT License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.

        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],

    # What does your project relate to?
    keywords='trustlines',

    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),
    package_dir={'trustlines-contracts': 'deploy'},

    # Alternatively, if you want to distribute just a my_module.py, uncomment
    # this:
    #   py_modules=["my_module"],

    # List run-time dependencies here.  These will be installed by pip when
    # your project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=['populus',
                      'web3',
                      'click'],

    # List additional groups of dependencies here (e.g. development
    # dependencies). You can install these using the following syntax,
    # for example:
    # $ pip install -e .[dev,test]
    extras_require={},

    # If there are data files included in your packages that need to be
    # installed, specify them here.  If using Python 2.6 or less, then these
    # have to be included in MANIFEST.in as well.
    package_data={},

    python_requires='>=3',

    # Although 'package_data' is the preferred approach, in some case you may
    # need to place data files outside of your packages. See:
    # http://docs.python.org/3.4/distutils/setupscript.html#installing-additional-files # noqa
    # In this case, 'data_file' will be installed into '<sys.prefix>/my_data'
    data_files=[('trustlines-contracts', ['project.json']),
                ('trustlines-contracts/build', ['build/contracts.json']),
                ('trustlines-contracts/contracts', list_files('contracts')),
                ('trustlines-contracts/contracts/lib', list_files('contracts/lib')),
                ('trustlines-contracts/contracts/tokens', list_files('contracts/tokens')),
                ],

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    entry_points="""
    [console_scripts]
    tl-deploy=tlcontracts.cli:cli
    """,
    cmdclass={
        'compile_contracts': CompileContracts,
        'build_py': BuildPyCommand,
    },
)
