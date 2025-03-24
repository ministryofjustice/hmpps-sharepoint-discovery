import logging
import os
import json
import requests
import re
from time import sleep
from classes.slack import Slack
from classes.service_catalogue import ServiceCatalogue
from classes.sharepoint import SharePoint

log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()

class Services:
  def __init__(self, sc_params, slack_params, log):
    self.sc = ServiceCatalogue(sc_params, log)
    self.sp = SharePoint(sp_params, log)
    self.slack = Slack(slack_params, log)
    self.log = log

def batch_process_sc_products(services, max_threads=10):
  sc = services.sc
  sp = services.sp
  log = services.log

  products = sc.get_all_records(sc.products_get)
  log.info(f'Processing batch of {len(products)} products...')
  sp_products = sp.get_sharepoint_lists('Products and Teams Main List', 'Team,ProductSet,ServiceArea')
  # log.info(f'Found {len(sp_products["value"])} products in SharePoint...')
  # print(sp_products)
  # for sp_product in sp_products['value']:
  #   if sp_product['fields']['ProductID'] == 'DPS117':
  #     print(sp_product)
  #   if not re.match(r'^.+$', sp_product['fields']['Product']):
  #     return "Invalid name"

  #   if not re.match(r'^[A-Z]{3,4}[0-9]{0,5}$', sp_product['fields']['ProductID']):
  #     return "Invalid productID"

  #   # legacyBool = True if sp_product['fields']['legacy'] == True else False
  #   subproductBool = True if sp_product['fields']['ProductType'] == "Subproduct" else False
  #   parent = None if sp_product['fields']['ParentProduct'] == "" else fetchID("products", "name", sp_product['fields']['ParentProduct'])
  #   # team = None if sp_product['fields']['team'] == "" else fetchID("teams", "name", sp_product['fields']['team'])
  #   # productSet = None if sp_product['fields']['productSet'] == "" else fetchID("product-sets", "name", sp_product['fields']['productSet'])
  #   # serviceArea = None if sp_product['fields']['serviceArea'] == "" else fetchID("service-areas", "name", sp_product['fields']['serviceArea'])
  #   # confluenceLink = ', '.join(sp_product['fields']['confluenceLink'].split('\n')) if 'confluenceLink' in sp_product['fields'] else None

  #   # product_data = {
  #   #   "p_id": sp_product['fields']['ProductID'],
  #   #   "name": sp_product['fields']['Product'],
  #   #   "subproduct": subproductBool,
  #   #   "parent": parent,
  #   #   "legacy": legacyBool,
  #   #   "description": sp_product['fields']['Description_x0028_SourceData_x00'],
  #   #   "team": team,
  #   #   "phase": sp_product['fields']['phase'],
  #   #   "product_set": productSet,
  #   #   "service_area": serviceArea,
  #   #   "delivery_manager": sp_product['fields']['ServiceOwnerString'],
  #   #   "product_manager": sp_product['fields']['TechnicalArchitectLookupId'],
  #   #   "lead_developer": sp_product['fields']['TechnicalArchitectLookupId'],
  #   #   "confluence_link": confluenceLink,
  #   #   "gdrive_link": sp_product['fields']['gDriveLink'],
  #   #   "slack_channel_id": sp_product['fields']['SlackchannelID'],
  #   #   "updated_by_id": None
  #   # }
  #   # print (product_data)
  #   print('****************************')



def main():
  logging.basicConfig(
    format='[%(asctime)s] %(levelname)s %(threadName)s %(message)s', level=log_level
  )
  log = logging.getLogger(__name__)

  # service catalogue parameters from environment variables
  sc_params = {
    'sc_api_endpoint': os.getenv('SERVICE_CATALOGUE_API_ENDPOINT'),
    'sc_api_token': os.getenv('SERVICE_CATALOGUE_API_KEY'),
    'sc_filter': os.getenv('SC_FILTER', ''),
  }

  # slack parameters from environment variables
  slack_params = {
    'slack_bot_token': os.getenv('SLACK_BOT_TOKEN'),
  }
  services = Services(sc_params, slack_params, log)

  log.info('Processing products...')
  qty = batch_process_sc_products(services, max_threads)
  log.info(f'Finished processing {qty} products.')
  return qty


if __name__ == '__main__':
  main()
