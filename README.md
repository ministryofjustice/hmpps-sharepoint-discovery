# hmpps-sharepoint-discovery

Synchronises SharePoint discovery data into Service Catalogue from Sharepoint Lists.

The job reads SharePoint lists and creates/updates/deletes records in Service Catalogue for:

- Teams
- Service Areas
- Product Sets
- Products

It also sends Slack notifications when records are processed.

## Product Slack channels

The SharePoint `SlackchannelID` value may contain a channel ID or name.
Discovery resolves its counterpart and stores `name|ID` in the Service Catalogue
`slack_channel_id` field. Surrounding whitespace is stripped; unresolved parts use
`none` (`name|none` or `none|ID`). Empty source values clear the field.

Resolution runs before comparison on every run, including for new products, so
channel renames are detected even when SharePoint has not changed. The
`slack_channel_name` field is not read or written. Consumers must parse the combined
value; removing the old field from the Service Catalogue schema is a separate change.
Products absent from SharePoint are not enriched.

The Slack bot requires `channels:read` and `groups:read` for channel lookups.
Private channels are only accessible where the bot has been added.

Run the unit tests with `uv run python -m unittest discover -s tests`.

## What This Job Processes

The job loads these SharePoint lists:

- Service Areas
- Product Set
- Teams
- Service Owners
- Product Managers
- Delivery Managers
- Lead Developers
- Products and Teams Main List
- Technical Architects
- Principal Technical Architect

## Requirements

- Python 3.13+
- `uv` for dependency management

## Local Setup

Install dependencies:

```bash
uv sync
```

Run the discovery job:

```bash
uv run python -u sharepoint_discovery.py
```

## Environment Variables

Required:

- `SERVICE_CATALOGUE_API_ENDPOINT`
- `SERVICE_CATALOGUE_API_KEY`
- `AZ_TENANT_ID`
- `SP_CLIENT_ID`
- `SP_CLIENT_SECRET`
- `SP_SITE_ID`
- `SLACK_BOT_TOKEN`

Optional:

- `SLACK_NOTIFY_CHANNEL`
- `SLACK_ALERT_CHANNEL`
- `LOG_LEVEL` (default: `INFO`)

## Local Testing Modes

Test without proxy (local only):

```bash
unset HTTPS_PROXY HTTP_PROXY NO_PROXY https_proxy http_proxy no_proxy
uv run python -u sharepoint_discovery.py
```

## Linting

Pre-commit Ruff checks are configured in:

- `.husky/pre-commit`

Run Ruff manually:

```bash
ruff check .
```
