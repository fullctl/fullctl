#!/bin/bash


service="$1"; shift
if [[ -z "${service}" ]]; then
  echo missing service name
  exit 1
fi

COMPOSE_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
PROJECT_NAME=$(basename $(git rev-parse --show-toplevel))

service_id=$(docker-compose -p $PROJECT_NAME -f $COMPOSE_DIR/docker-compose.yml ps -q $service)

if [[ -z "${service_id}" ]]; then
  echo error finding service id
  exit 1
fi

docker exec -it $service_id "$@"
