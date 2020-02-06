 #!/usr/bin/env sh
 set -e

 VERSION=$(python3 ./calc_npm_version.py)
 npm version "$VERSION" --allow-same-version
