# Dockerized ASReview and Search Application

This repository contains the Docker setup for the ASReview and Search application. Follow the instructions below to set up and run the application on your local machine.

## Prerequisites

- Docker: [Install Docker](https://docs.docker.com/get-docker/)
- Docker Compose: [Install Docker Compose](https://docs.docker.com/compose/install/)

## Files

- `Dockerfile`: Docker configuration for building the search application.
- `docker-compose.yml`: Docker Compose configuration for orchestrating the containers.
- `.env`: Environment variables configuration (optional).
- `app_AI.py`: The main search application script.
- `requirements.txt`: Python dependencies for the search application.
- `asreview_config.toml`: Configuration file for ASReview.
- `asreview.conf`: Nginx configuration file for ASReview.

## Setup Instructions

1. **Clone the Repository:**

   ```sh
   git clone <repository_url>
   cd <repository_directory>
