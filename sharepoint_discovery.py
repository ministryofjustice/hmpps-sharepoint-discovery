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
import sys
import logging

# Classes for the various parts of the script
# from classes.health import HealthServer
from classes.service_catalogue import ServiceCatalogue
from classes.sharepoint import SharePoint
from classes.slack import Slack

# Components
import processes.teams as teams
import processes.product_sets as productSets
import processes.service_areas as serviceAreas
import processes.products as products
import processes.scheduled_jobs as sc_scheduled_job
from utilities.discovery import job

log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()


class Services:
  def __init__(self, sc_params, sp_params, slack_params, log):
    self.slack = Slack(slack_params, log)
    self.sc = ServiceCatalogue(sc_params, log)
    self.sp = SharePoint(sp_params, log)
    self.log = log

def should_send_slack_notification(processed_messages):
  for message in processed_messages:
    if "processed" in message:
      parts = message.split("processed")
      if len(parts) > 1:
        try:
          count = int(parts[1].split()[0])
          if count > 0:
            return True
        except ValueError:
          continue
  return False  # All categories have 0 processed

def main():
  logging.basicConfig(
    format='[%(asctime)s] %(levelname)s %(threadName)s %(message)s', level=log_level
  )
  log = logging.getLogger(__name__)

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
  services = Services(sc_params, sp_params, slack_params, log)
  sc = services.sc
  slack = services.slack
  sp = services.sp

  # Send some alerts if there are service issues

  if not sc.connection_ok:
    slack.alert('*Sharepoint Discovery failed*: Unable to connect to the Service Catalogue')
    raise SystemExit()

  if not sp.connection_ok:
    job.error_messages.append('Unable to connect to Sharepoint Graph API')
    sc_scheduled_job.update(services, 'Failed')
    slack.alert('*Sharepoint Discovery failed*: Unable to connect to Sharepoint Graph API')
    raise SystemExit()
  
  try:
    # Process Teams 
    log.info('Processing teams...')
    processed_teams = teams.process_sc_teams(services)

    # Process Product Sets
    log.info('Processing product sets ...')
    processed_product_sets = productSets.process_sc_product_sets(services)

    # Process Service areas
    log.info('Processing service areas...')
    processed_service_area = serviceAreas.process_sc_service_areas(services)

    # Process products
    log.info('Batch processing products...')
    processed_products = products.process_sc_products(services)
    
    # Combine output of all the processes
    processed_messages = []
    processed_messages.extend(processed_teams)
    processed_messages.extend(processed_product_sets)
    processed_messages.extend(processed_service_area)
    processed_messages.extend(processed_products)

    if should_send_slack_notification(processed_messages):
      log.info("Sending Slack notification...")
      slack.notify('\n'.join(processed_messages))
    else:
      log.info("No records processed, not sending Slack notification")
  
  except Exception as e:
    job.error_messages.append(f"Sharepoint discovery job failed with error: {e}")
    slack.alert(f"*Sharepoint Discovery failed*: {e}")
    log.error(f"Sharepoint discovery job failed with error: {e}")

  if job.error_messages:
    sc_scheduled_job.update(services, 'Errors')
    log.info("SharePoint discovery job completed  with errors.")
  else:
    sc_scheduled_job.update(services, 'Succeeded')
    log.info("SharePoint discovery job completed successfully.")

if __name__ == '__main__':
  main()
