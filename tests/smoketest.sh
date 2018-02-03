#!/usr/bin/env bash
testrpc-py &
sleep 3
docker run --net="host" contracts deploy/deploy_testrpc.py
