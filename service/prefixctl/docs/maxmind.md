## Env Var:
- `MAXMIND_ACCOUNT_ID` - Maxmind account id
- `MAXMIND_API_KEY` - Maxmind API key
- `MAXMIND_DATABASE_URL` - Maxmind database URL = "https://download.maxmind.com/geoip/databases"
- `MAXMIND_DATABASE_FOLDER_NAME_PREFIX` - Maxmind database folder name prefix = "GeoLite2"
- `MAXMIND_BATCH_CHUNK_SIZE` - The count per chunk the bulk update operation = 1000

## Task Scheduling:
Add a new scheduler for the new task in django admin, see screenshot below

Set the start of the scheduler under date and time

Set repeat to true to repeat the task

Set interval 2592000 to represent monthly (30 days)

[![maxmind-task-scheduler.png](https://gitlab.fullctl.com/fullctl/prefixctl/-/blob/prep-release/docs/img/maxmind-task-scheduler.png)]()

```
{
 "tasks": [
   {
     "op": "maxmind_load_database_task",
     "param": {
       "args": [],
       "kwargs": {}
     }
   }
 ]
}
```


## Available columns
### City Data:
- network
- latitude
- longitude
- geoname_id
- is_anycast
- postal_code
- accuracy_radius
- is_anonymous_proxy
- is_satellite_provider
- registered_country_geoname_id
- represented_country_geoname_id

### Country Data:
- network
- geoname_id
- is_anycast
- is_anonymous_proxy
- is_satellite_provider
- registered_country_geoname_id
- represented_country_geoname_id

## Location reference data:
### City:
- city_name
- time_zone
- geoname_id
- metro_code
- locale_code
- country_name
- continent_code
- continent_name
- country_iso_code
- subdivision_1_name
- subdivision_2_name
- is_in_european_union
- subdivision_1_iso_code
- subdivision_2_iso_code

### Country:
- geoname_id
- locale_code
- continent_code
- continent_name
- country_iso_code
- country_name
- is_in_european_union