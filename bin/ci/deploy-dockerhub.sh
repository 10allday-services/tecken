#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# This is meant to be run by CI.

set -e

# Usage: retry MAX CMD...
# Retry CMD up to MAX times. If it fails MAX times, returns failure.
# Example: retry 3 docker push "mozilla/tecken:$TAG"
function retry() {
    max=$1
    shift
    count=1
    until "$@"; do
        count=$((count + 1))
        if [[ $count -gt $max ]]; then
            return 1
        fi
        echo "$count / $max"
    done
    return 0
}

# configure docker creds
retry 3  echo "$DOCKER_PASSWORD" | docker login -u="$DOCKER_USERNAME" --password-stdin

# docker tag and push git branch to dockerhub
if [ -n "$1" ]; then
    [ "$1" == main ] && TAG=latest || TAG="$1"
    docker tag tecken:build "mozilla/tecken:$TAG" ||
        (echo "Couldn't tag tecken:build as mozilla/tecken:$TAG" && false)
    retry 3 docker push "mozilla/tecken:$TAG" ||
        (echo "Couldn't push mozilla/tecken:$TAG" && false)
    echo "Pushed mozilla/tecken:$TAG"
fi
