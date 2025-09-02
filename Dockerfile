FROM python:3.12-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:0.8.12 /uv /uvx /bin/

# Copy the project into the image
ADD . /app

# Sync the project into a new environment, asserting the lockfile is up to date
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        build-essential \
        gcc \
        python3-dev \
        libpq-dev \
        weasyprint \
    && rm -rf /var/lib/apt/lists/*

    
RUN uv sync --locked

# Make port 8000 available to the world outside this container
EXPOSE 8000

RUN chmod +x docker_start.sh

# Presuming there is a `my_app` command provided by the project
CMD ["./docker_start.sh"]
