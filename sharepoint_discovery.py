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
venv_site_packages = os.path.join('/Users/sandhya.gandalwar/sre/new_sharepoint_discovery/venv/lib/python3.9/site-packages')
sys.path.insert(0, venv_site_packages)

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

log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()

class Services:
  def __init__(self, sc_params, sp_params, slack_params, log):
    self.slack = Slack(slack_params, log)
    self.sc = ServiceCatalogue(sc_params, log)
    self.sp = SharePoint(sp_params, log)
    self.log = log

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

  services = Services(sc_params, sp_params, slack_params, log)

  # Send some alerts if there are service issues

  if not services.sc.connection_ok:
    services.slack.alert('*Sharepoint Discovery failed*: Unable to connect to the Service Catalogue')
    raise SystemExit()

  if not services.sp.connection_ok:
    services.slack.alert('*Sharepoint Discovery failed*: Unable to connect to Sharepoint Graph API')
    raise SystemExit()

  # # Process Teams 
  # log.info('Processing teams...')
  # processed_teams = teams.process_sc_teams(services)

  # # Process Product Sets
  # log.info('Processing product sets ...')
  # processed_product_sets = productSets.process_sc_product_sets(services)

  # # Process Service areas
  # log.info('Processing service areas...')
  # processed_service_area = serviceAreas.process_sc_service_areas(services)

  #Process products
  log.info('Batch processing products...')
  processed_products = products.process_sc_products(services)
  
  # create_summary(services, processed_components, processed_products, processed_teams)
  # create_summary(services, processed_components, processed_products, force_update)

if __name__ == '__main__':
  main()
