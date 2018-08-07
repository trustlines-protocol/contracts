#!/usr/bin/env bash

set -e

DOCKER_REPO=trustlines/contracts
LOCAL_IMAGE=contracts

echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USER" --password-stdin

version=$(docker run --entrypoint '' --rm $LOCAL_IMAGE cat VERSION | tr '+' '_')

echo "Tagging with $version"
echo "=====> pushing to dockerhub"

set -x

docker tag $LOCAL_IMAGE $DOCKER_REPO:$version
docker push $DOCKER_REPO:$version

docker tag $LOCAL_IMAGE $DOCKER_REPO:latest
docker push $DOCKER_REPO:latest
