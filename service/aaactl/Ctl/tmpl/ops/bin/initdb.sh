#!/bin/bash

read -p "postgres admin user [postgres]: " psql_user
psql_user=${psql_user:-postgres}

SQL_DB="CREATE DATABASE {{ db.name }};"
SQL_USER="CREATE USER {{ db.user }} WITH PASSWORD '{{ db.password }}';"
SQL_PERMS="GRANT ALL PRIVILEGES ON DATABASE {{ db.name }} TO {{ db.user }};"
SQL_CONF="ALTER ROLE {{ db.user }} SET client_encoding TO 'utf8';
ALTER ROLE {{ db.user }} SET default_transaction_isolation TO 'read committed';
ALTER ROLE {{ db.user }} SET timezone TO 'UTC';"

echo "running psql as $psql_user"

echo "creating database {{ db.name }} ..."
sudo -iu $psql_user -H -- psql -c "$SQL_DB"
echo "creating user {{ db.user }} ..."
sudo -iu $psql_user -H -- psql -c "$SQL_USER"
echo "granting rights on {{ db.name }} to user {{ db.user }} ..."
sudo -iu $psql_user -H -- psql -c "$SQL_PERMS"
echo "role settings for user {{ db.user }} ..."
sudo -iu $psql_user -H -- psql -c "$SQL_CONF"
