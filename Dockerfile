FROM ghcr.io/ministryofjustice/hmpps-python:python3.13-alpine AS base

# initialise uv
COPY pyproject.toml .
RUN uv sync

# create the /app/trivy directory f
# copy the dependencies from builder stage
COPY classes classes
COPY processes processes
RUN chown -R appuser:appgroup /app/classes /app/processes
COPY --chown=appuser:appgroup  ./sharepoint_discovery.py /app/sharepoint_discovery.py

# update PATH environment variable
ENV PATH=/home/appuser/.local:/app:$PATH
USER 2000

CMD [ "uv", "run", "python", "-u", "/app/sharepoint_discovery.py" ]
