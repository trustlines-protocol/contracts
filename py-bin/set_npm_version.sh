 #!/usr/bin/env sh
 set -e

 VERSION=$(python3 -c 'from setuptools_scm import get_version; print(get_version(root="..").replace(".dev", "-dev").replace("+", "."))')
 npm version "$VERSION" --allow-same-version
