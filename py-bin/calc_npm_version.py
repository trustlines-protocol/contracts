#! bin/env python3
import re
from setuptools_scm import get_version


def is_prerelease(version: str):
    # Compare allowed pre release ids in circle ci config
    return bool(re.match(r"[0-9]+(\.[0-9]+)*(a|b|rc)[0-9]+", version))


def to_npm_version(python_version):
    version = python_version
    if is_prerelease(version):
        version = re.sub(r"([0-9]+(\.[0-9]+)*)((a|b|rc)[0-9]+)", r"\1-\3", version)
    else:
        version = version.replace(".dev", "-dev")

    version = version.replace("+", ".")

    return version


if __name__ == "__main__":
    print(to_npm_version(get_version(root="..")))


# these tests are not run automatically currently, so make sure to run them locally
def test_is_prerelease():
    for version, result in [
        ("1.0", False),
        ("1.0+a4dd", False),
        ("1.0.dev5+rcab343", False),
        ("1.0a1", True),
        ("1.0b5.dev+aa", True),
    ]:
        assert is_prerelease(version) == result


def test_to_npm_version():
    for python_version, npm_version in [
        ("1.0", "1.0"),
        ("1.0a1", "1.0-a1"),
        ("1.0.2b4", "1.0.2-b4"),
        ("1.0.dev3", "1.0-dev3"),
        ("1.0a5.dev+abcd", "1.0-a5.dev.abcd"),
        ("1.0a5.dev+a5bccrc4", "1.0-a5.dev.a5bccrc4"),
    ]:
        assert to_npm_version(python_version) == npm_version
