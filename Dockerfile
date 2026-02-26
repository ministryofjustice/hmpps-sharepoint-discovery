FROM ghcr.io/ministryofjustice/hmpps-python:python3.13-alpine AS base

# Add git for pulling uv packages
RUN apk add --no-cache git

# initialise uv
COPY pyproject.toml .
RUN uv sync

# create the /app/trivy directory f
# copy the dependencies from builder stage
COPY processes processes
COPY --chown=appuser:appgroup  ./sharepoint_discovery.py /app/sharepoint_discovery.py

CMD [ "uv", "run", "python", "-u", "/app/sharepoint_discovery.py" ]
