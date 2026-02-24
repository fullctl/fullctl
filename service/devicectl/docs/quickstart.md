# DEVICECTL

## Quickstart

## Quickstart

## Quickstart

To get a local repo and change into the directory:
```sh
git clone git@github.com:20c/devicectl
cd devicectl
```

Devicectl is containerized with Docker. First we want to copy the example environment file:
```sh
cp Ctl/dev/example.env Ctl/dev/.env
```
Any of the env variables can be changed, and you should set your own secret key.

You can launch the app via:
```sh
Ctl/dev/compose.sh build
Ctl/dev/compose.sh up
```


The first time you run `compose.sh up` it will create a docker volume named `devicectldev_postgres_data` and will initialize the Postgres database with a user according to the settings you've provided. Generally, the compose script will automatically perform migrations within the Django app; however, the first time you run `compose.sh up` you may find that the Django app is unable to perform migrations because the Postgres database is still being initialized. To solve this, simply wait until the Postgres db is initialized, and then stop the Docker containers with

```sh
Ctl/dev/compose.sh down
```


On running `compose.sh up` any subsequent time, the Django app will be able to run migrations properly. Additionally, if you're starting up the app for the first time, you will want to `ssh` into the Django container and run a few additional commands. Do this **without** the services currently running, again stopping your containers with `compose.sh down` if necessary. `Ctl/dev/run.sh /bin/sh` will launch the services properly and ssh into the Django container for you:


```sh
Ctl/dev/run.sh /bin/sh
cd main
manage createsuperuser
manage createcachetable
manage devicectl_peeringdb_sync
```


## Notable env variables

- `SECRET_KEY`
- `DATABASE_ENGINE`
- `DATABASE_HOST`
- `DATABASE_NAME`
- `DATABASE_USER`
- `DATABASE_PASSWORD`

## On env variables

The environment file you copied from `example.env` contains variables for configuring both the Django and Postgres services- if you change the database name, user, or password, you must ensure the values still match between the Django and Postgres settings. The Django database variables are passed directly into the Django application settings so all five `DATABASE_` settings should remain defined.


## API Key auth

### Method 1: HTTP Header

```
Authorization: bearer {key}
```

```
curl -X GET https://localhost/api/20c/ix/ -H "Authorization: bearer {key}"
```

### Method 2: URI parameter

```
?key={key}
```

## Generate openapi schema

```sh
python manage.py generateschema > django_devicectl/static/devicectl/openapi.yaml
cp django_devicectl/static/devicectl/openapi.yaml ../docs/openapi.yaml
```
