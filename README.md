# Dockerized ASReview and Search Application

This repository contains the Docker setup for the ASReview and Search application. It includes instructions for building, running, and pushing the application Docker images to the Snowflake registry. **Note:** The Docker containers must be compatible with linux/amd64. If you encounter issues on other platforms, you may need to rebuild the images using Docker Buildx.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)
- [Docker Buildx](https://docs.docker.com/buildx/working-with-buildx/) (included in recent Docker versions)

## Files

- **Dockerfile**: Docker configuration for building the search application.
- **docker-compose.yml**: Docker Compose configuration for orchestrating the containers.
- **.env**: Environment variables configuration (optional).
- **app_AI.py**: The main search application script.
- **requirements.txt**: Python dependencies for the search application.
- **asreview_config.toml**: Configuration file for ASReview.
- **asreview.conf**: Nginx configuration file for ASReview.

## Setup Instructions

1. **Clone the Repository:**

   ```
   git clone <repository_url>
   cd <repository_directory>
   ```

2. Build Docker Images for linux/amd64 Compatibility:
   
   To ensure the images are compatible with linux/amd64 (required by the Snowflake registry), rebuild them using Docker Buildx. For example, to build the search application image, run:
   
   ```
   docker buildx build --platform linux/amd64 -t your_local_image_name:latest .
   ```
   Replace your_local_image_name with your preferred local image name. You can repeat this step for any image (e.g., my-asreview-image, file_upload_service, or nginx).
   
3. Run the Application Locally (Optional):

If you wish to run the application locally, you can use Docker Compose:

```
docker-compose up --build
```

## Pushing Docker Images to Snowflake
To push your Docker images to the Snowflake registry, follow these steps:

1. Set the Registry URL Environment Variable:
Define your Snowflake registry URL. For example:

```
export REPO_URL='path_to_repository'/scs_db/data_schema/scs_repository
```
2. Log in to the Snowflake Registry:

Authenticate with your Snowflake registry using:

```
docker login $REPO_URL
```

3. Tag Your Docker Image:

Tag your locally built Docker image so that it points to the Snowflake registry. Replace <image_id> with your image’s ID and <image_name> with the desired name.

```
docker tag <image_id> $REPO_URL/<image_name>:latest
```

For example, if your local image has an ID of 64d5d9d2cf5e and you want to push it as my-asreview-image, run:

```
docker tag 64d5d9d2cf5e $REPO_URL/my-asreview-image:latest
```

4. Push the Docker Image:

Push the tagged image to the Snowflake registry with:

```
docker push $REPO_URL/<image_name>:latest
```
Using the example above:

```
docker push $REPO_URL/my-asreview-image:latest
```

Repeat the tagging and pushing process for any additional images (e.g., file_upload_service, nginx, or search_app) that you need to upload.

## Rebuilding Images for linux/amd64 Compatibility
If you find that your images are not built for linux/amd64 (which is required for the Snowflake registry), rebuild them using Docker Buildx. For example, to rebuild the search_app image:

```
docker buildx build --platform linux/amd64 -f Dockerfile -t $REPO_URL/search_app:latest .
```

## Troubleshooting
Missing Files During Build:
If you receive errors like COPY requirements.txt .: not found, verify that your build context includes the required files and that the file paths in your Dockerfile are correct.

Push Errors / HTTP Status Issues:
If the push fails (e.g., with a 500 Internal Server Error or connection timeouts), double-check your network connection, registry credentials, and that the $REPO_URL environment variable is set correctly.

Platform Compatibility Issues:
Ensure that you are explicitly building for linux/amd64 using the --platform linux/amd64 flag if you are on a non-amd64 host.
