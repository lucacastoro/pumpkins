#!/bin/bash

ROOT=$(readlink -e $(dirname $0))
docker run --rm -it -v $ROOT:/staging:ro -w /staging pumpkins python3 -B -m pytest -p no:cacheprovider -v $@
