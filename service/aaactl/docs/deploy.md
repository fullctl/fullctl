# Deploy

Instructions on how to deploy the 20c auth server environment

## Development Instance

Ensure docker and docker-compose are installed.

Copy `Ctl/dev/example.env` to `Ctl/dev/.env` and edit.

To bring up the full dev services, run:

```sh
Ctl/dev/compose.sh up
```

Which is currently just `docker-compose -f Ctl/dev/docker-compose.yml $@`

This will run a postgres database and the account service in containers and mount the src directory so it refreshes the server whenever a file changes.

Any container commands can then be run from `Ctl/dev/run.sh`

Create managed  permissions
```sh
Ctl/dev/run.sh loaddata fixtures/fixture.perms.json
```

First time running, create a new superuser to use to login:
```sh
Ctl/dev/run.sh createsuperuser
```

To bring up just a single service:
```sh
Ctl/dev/compose.sh up $SERVICE
```

To rebuild a container:
```sh
Ctl/dev/compose.sh build account_django
```

To run all tests:
```sh
Ctl/dev/run.sh run_tests
```

To drop into a shell with pytest settings configured and the virtualenv activated:
```sh
Ctl/dev/run.sh test_mode
```
from there the user can run specific tests, for example:
```
pytest tests/test_account_api.py::test_org_users
```


## Configure instance

### Service bridge

#### Setup internal api key

Go to `https://$ACCOUNT_SERVICE_URL/admin/account/internalapikey/add/` and create
a new internal api key.

This key is used for internal communications between aaactl and the various fullctl services.

Under `Internal API Key Permissions` for the key also create the following entry:

- namespace: `*.*`
- permissions: `crud`

This key has access to everything - never share it.

#### Task processor

In order for aaactl to sync org and user information changes to other fullctl
services in real time, at least one task processor needs to be running.

Start a task processor by running

```sh
python manage.py fullctl_poll_tasks --workers 4
```

### oAuth

#### Setup PDB oauth2 client

Redirect goes to:

`https://$ACCOUNT_SERVICE_URL/social/complete/peeringdb/`

For example:

`https://account.dev8.20c.com/social/complete/peeringdb/`
￼
￼
#### Setup Google oauth2 client

https://$ACCOUNT_SERVICE_URL/social/complete/google-oauth2/

https://account.dev8.20c.com/social/complete/google-oauth2/

#### Setup oauth2 provider

Create an application for FullCtl at /admin/oauth2_provider/application

Redirect to https://`$FULLCTL_URL`/complete/twentyc/

For example:

https://fullctl.dev8.20c.com/complete/twentyc/


* client type: confidential
* authoriozation grant type: authorization code
* name: fullctl
* skip authorization: true
* client id: generated or if fullctl already set up use the client id set up there
* secret: generated or if fullctl already set up use the secret setup there

-----


## **OLD** Ctl

```sh
yum install -y python3-devel openldap-devel
```

Set up a virtual environment that has ctl installed

```sh
python3.6 -m virtualenv venv
. venv/bin/activate
pip install ctl pipenv jinja2 tmpl
```

## **OLD** Developer Instance

### Copy deploy config for a dev deploy

Copy the example dev config and make changes where necessary

```sh
cp Ctl/dev.example.yaml Ctl/dev.yaml
vim Ctl/dev.yaml
```

### Create passwords file for delpoy

You will need to set up your deploy passwords (db etc.)

```sh
mkdir Ctl/.state/dev/ -p
vim Ctl/.state/dev/passwords.yaml
chmod 600 Ctl/.state/dev/passwords.yaml
```

```yaml
db:
  password: ...
django:
  secret_key: ...

recaptcha:
  private_key: ...
  public_key: ...

oauth:
  google:
    client_id: ...
    secret: ...
  peeringdb:
    client_id: ...
    secret: ...

billing:
  stripe:
    public_key: ...
    secret_key: ...
```

### Virtualenv

Build and deploy the virtualenv for the developer instance. This will
be a separate venv from the one you are currently using.

```sh
ctl deploy_venv dev .
```

virtual environment will be deployed to

```sh
~/srv/account.20c.com/dev/venv
```

This process may take a while (5mins)

### Project

Deploy the django project for the developer instance

```sh
ctl deploy_project dev .
```

django project will be deployed to

```sh
~/srv/account.20c.com/dev/account_service
```

### Create Database

Run the following command to set up the postgres database and user for the dev
instance

Run as either `root` or a user with `sudo` access

This will setup the postgres database (@grizz maybe look at it first before you run it :P)

```sh
source ~/srv/account.20c.com/dev/ops/bin/initdb.sh
```

#### Migrate database

```sh
. ~/srv/account.20c.com/dev/venv/bin/activate
cd account_service
python manage.py migrate
```

#### Run from docker

Make a file, in this case, `LOCAL/dev.env`

```sh
DATABASE_HOST=10.203.0.153
DATABASE_PASSWORD=SUPERS3CR3T
```

```sh

time docker build -t $DKR_PROJ:$DKR_TAG -f Dockerfile  .
docker run -it --net=host --env-file=LOCAL/dev.env \
  -v `pwd`/src/account_service/settings/:/venv/lib/python3.6/site-packages/account_service/settings/
  $DKR_PROJ:$DKR_TAG runserver 127.0.0.1:7002

#  718  docker run -it --net=host --env-file=LOCAL/dev.env   -v `pwd`/src/account_service/settings/:/venv/lib/python3.6/site-packages/account_service/settings/   $DKR_PROJ:$DKR_TAG
#  719  docker run -it --net=host --env-file=LOCAL/dev.env   -v `pwd`/src/account_service/settings/:/venv/lib/python3.6/site-packages/account_service/settings/   $DKR_PROJ:$DKR_TAG  runserver 127.0.0.1:7002


```

##### FATAL: Peer authentication failed

In case of postgres authentication servers, make sure the django db user
is allowed to connect to the db through md5 authentication

We can fix this by editing the hba config file

First find the file location

```sh
sudo -iu postgres -H -- psql -c "show hba_file;"
```

Then edit it and add the following line to the top

```
local all account_service md5
```

Save and restart the postgres service

```sh
sudo service postgresql-11 reload
```

