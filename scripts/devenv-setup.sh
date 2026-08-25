#!/bin/bash

REPOSITORIES="fullctl aaactl ixctl pdbctl peerctl devicectl prefixctl"
SERVICES="aaactl_web ixctl_web pdbctl_web peerctl_web"
BRANCH="prep-release"

echo "Setting up new fullctl dev environemnt"
echo "Cloning repositories"

for name in $REPOSITORIES
do
  if [ ! -d "$name" ]; then
    git clone git@github.com:fullctl/$name
  fi
done

for name in $REPOSITORIES
do
  cd "$name"
  git checkout $BRANCH
  if [ ! -f "Ctl/dev/.env" ]; then
    echo "Copying base env settings for $name"
    cp Ctl/dev/example.env Ctl/dev/.env
  fi
  cd ..
done

cd fullctl

echo "Building and starting database container"
uv run Ctl/dev/compose.sh up -d postgres

echo "Building containers"
uv run Ctl/dev/compose.sh build

for name in $SERVICES
do
  uv run Ctl/dev/run.sh $name migrate
  uv run Ctl/dev/run.sh $name createcachetable
  if [ $name = "aaactl_web" ]; then
    uv run Ctl/dev/run.sh $name loaddata fixtures/fixture.full-perms.json
    echo "Creating django admin account (ctrl+c if already exists)"
    uv run Ctl/dev/run.sh $name createsuperuser
  fi
  if [ $name = "pdbctl_web" ]; then
    uv run Ctl/dev/run.sh $name fullctl_peeringdb_sync
  fi
done
