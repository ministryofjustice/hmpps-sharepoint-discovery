FROM ghcr.io/ministryofjustice/hmpps-python:python3.13-alpine AS base

# Add git for pulling uv packages
USER 0
RUN apk add --no-cache git
USER 2000

# initialise uv
COPY pyproject.toml .
RUN uv sync

# create the /app/trivy directory f
# copy the dependencies from builder stage
COPY processes processes
COPY --chown=appuser:appgroup  ./sharepoint_discovery.py /app/sharepoint_discovery.py

CMD [ "uv", "run", "python", "-u", "/app/sharepoint_discovery.py" ]
