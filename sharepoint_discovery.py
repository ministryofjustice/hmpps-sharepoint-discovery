#!/usr/bin/env python
"""Sharepoint discovery - queries the Sharepoint Graph API for lists of lists and populates service catalogue with the results.

Required environment variables
------------------------------

Sharepoint (Credentials for Discovery app that has access to Sharepoint lists)
- TENANT_ID: Azure Tenant ID
- SP_CLIENT_ID: Sharepoint Client ID
- SP_CLIENT_SECRET: Sharepoint Client Secret
- SP_SITE_ID: Sharepoint Site ID

Service Catalogue
- SERVICE_CATALOGUE_API_ENDPOINT: Service Catalogue API endpoint
- SERVICE_CATALOGUE_API_KEY: Service

- SLACK_BOT_TOKEN: Slack Bot Token

Optional environment variables
- SLACK_NOTIFY_CHANNEL: Slack channel for notifications
- SLACK_ALERT_CHANNEL: Slack channel for alerts
- LOG_LEVEL: Log level (default: INFO)

"""

import os

# hmpps-python-lib
from hmpps import ServiceCatalogue, Slack
from hmpps.services.job_log_handling import log_error, log_info, job

# local classes for the various parts of the script
from classes.sharepoint import SharePoint

# Components
import processes.teams as teams
import processes.product_sets as productSets
import processes.service_areas as serviceAreas
import processes.products as products


class Services:
  def __init__(self, sc_params, sp_params, slack_params):
    self.slack = Slack(slack_params)
    self.sc = ServiceCatalogue(sc_params)
    self.sp = SharePoint(sp_params)


def log_info_u(message):
  log_info('')
  log_info(message)
  log_info(f'{"=" * len(message)}')
  log_info('')


def should_send_slack_notification(processed_messages):
  for message in processed_messages:
    if 'processed' in message:
      parts = message.split('processed')
      if len(parts) > 1:
        try:
          count = int(parts[1].split()[0])
          if count > 0:
            return True
        except ValueError:
          continue
  return False  # All categories have 0 processed


def main():
  #### Create resources ####
  # service catalogue parameters
  sc_params = {
    'url': os.getenv('SERVICE_CATALOGUE_API_ENDPOINT'),
    'key': os.getenv('SERVICE_CATALOGUE_API_KEY'),
    'filter': os.getenv('SC_FILTER', ''),
  }

  # Sharepoint parameters
  sp_params = {
    'az_tenant_id': os.getenv('AZ_TENANT_ID'),
    'sp_client_id': os.getenv('SP_CLIENT_ID'),
    'sp_client_secret': os.getenv('SP_CLIENT_SECRET'),
    'sp_site_id': os.getenv('SP_SITE_ID'),
  }
  # Slack parameters
  slack_params = {
    'token': os.getenv('SLACK_BOT_TOKEN'),
    'notify_channel': os.getenv('SLACK_NOTIFY_CHANNEL', ''),
    'alert_channel': os.getenv('SLACK_ALERT_CHANNEL', ''),
  }
  job.name = 'hmpps-sharepoint-discovery'
  services = Services(sc_params, sp_params, slack_params)
  sc = services.sc
  slack = services.slack
  sp = services.sp

  # Send some alerts if there are service issues

  if not sc.connection_ok:
    slack.alert(
      '*Sharepoint Discovery failed*: Unable to connect to the Service Catalogue'
    )
    raise SystemExit()

  if not sp.connection_ok:
    log_error('Unable to connect to Sharepoint Graph API')
    sc.update_scheduled_job('Failed')
    slack.alert(
      '*Sharepoint Discovery failed*: Unable to connect to Sharepoint Graph API'
    )
    raise SystemExit()

  try:
    # Process Teams
    log_info_u('Processing teams')
    processed_teams = teams.process_sc_teams(services) or []

    # # Process Product Sets
    log_info_u('Processing product sets')
    processed_product_sets = productSets.process_sc_product_sets(services) or []

    # # Process Service areas
    log_info_u('Processing service areas')
    processed_service_area = serviceAreas.process_sc_service_areas(services) or []

    # Process products
    log_info_u('Batch processing products')
    processed_products = products.process_sc_products(services) or []

    # Combine output of all the processes
    summary_header = '*SharePoint Discovery Summary*'
    processed_messages = [summary_header]
    processed_messages.extend(processed_teams)
    processed_messages.extend(processed_product_sets)
    processed_messages.extend(processed_service_area)
    processed_messages.extend(processed_products)

    if should_send_slack_notification(processed_messages):
      log_info('Sending Slack notification')
      slack.notify('\n'.join(processed_messages))
    else:
      log_info('No records processed, not sending Slack notification')

  except Exception as e:
    log_error(f'Sharepoint discovery job failed with error: {e}')
    slack.alert(f'*Sharepoint Discovery failed*: {e}')
    log_error(f'Sharepoint discovery job failed with error: {e}')

  if job.error_messages:
    sc.update_scheduled_job('Errors')
    log_info('SharePoint discovery job completed  with errors.')
  else:
    sc.update_scheduled_job('Succeeded')
    log_info('SharePoint discovery job completed successfully.')


if __name__ == '__main__':
  main()
