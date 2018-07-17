#!/usr/bin/env bash
set -ev
testrpc-py &
sleep 3
docker run --net="host" contracts test
