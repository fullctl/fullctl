# Install

RegCtl runs in a docker container.

## Prerequisites

### Google API key for geocoding (optional)

RegCtl uses the Google Maps API for geocoding. You will need to create a Google API key and enable the Geocoding API.

Set up your credentials at https://console.cloud.google.com/apis/credentials.

1. Add an API key
2. Make sure the API is credentialed to use the Geocoding API

## 1. Make sure .env file exists

```bash
cp Ctl/dev/env.example Ctl/dev/.env
```

## 2. Set up Google API key (optional)

Edit the .env file and set the following variables:

```bash
GOOGLE_MAPS_API_KEY=your_google_api_key
```

If no API key is provided, the geocoding data points will be empty.

## 3. Build the docker image

```bash
Ctl/dev/compose.sh build
```

## 4. Set running port

In your environment (not in the .env file), set the port you want to run the container on:

```bash
export FASTAPI_PORT=8000
```

## 5. Run the docker container

```bash
Ctl/dev/compose.sh up
```