# Deployment Guide

This guide covers running the assistant in containers and in production.

## Docker

The repository includes a multi-stage Dockerfile. The build stage installs dependencies into a virtual environment, and the runtime stage copies only that environment and the application code, which keeps the final image small.

Build the image with `docker build -t assistant .` and start it with `docker run -p 8000:8000 --env-file .env assistant`. The container listens on port 8000 and runs Uvicorn with two worker processes by default.

The image runs as a non-root user named `app`. Do not mount the source directory into the container in production, because that bypasses the image's dependency lock.

## Docker Compose

The compose file starts two services: the API and MongoDB. MongoDB data is kept in a named volume called `mongo-data`, so restarting the stack does not lose users or chat history.

The vector database is embedded in the API process. Its files live in the `chroma_db` directory, which is mounted as a separate volume named `chroma-data`. Back up both volumes together, because the vector store and MongoDB must stay consistent.

## Health Checks

The `/health` endpoint returns `{"status": "healthy"}` when the process is running. The compose file polls it every 30 seconds with a 5 second timeout and marks the container unhealthy after 3 consecutive failures.

The health endpoint does not check MongoDB. A separate readiness check should be used by load balancers that need to know whether the database is reachable.

## Environment Variables

Configuration is read from environment variables, validated at startup. The application refuses to start if a required value such as API_KEY or JWT_SECRET_KEY is missing, rather than failing later on the first request.

Set MOCK_MODE to false in production; when it is true, chat responses are generated locally without calling the language model. Set FRONTEND_URL to the exact origin of the web client, because it is the only origin allowed by CORS.

## Scaling

Because the vector store is embedded, run a single API replica per `chroma_db` volume. To scale horizontally, move the vector store to a client-server deployment first; two replicas writing to the same embedded store can corrupt its index.
