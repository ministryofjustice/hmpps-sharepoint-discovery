import os
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

def process_sc_product_sets(services, max_threads=10):
  sc = services.sc
  sp = services.sp
  log = services.log

  sc_product_set_data = sc.get_all_records(sc.product_sets_get)
  log.info(f'Found {len(sc_product_set_data)} product sets in Service Catalogue before processing')
  sp_product_sets = sp.get_sharepoint_lists('Product Set','ProductSetID,ProductSet')
  log.info(f'Found {len(sp_product_sets["value"])} product sets in SharePoint...')
  sp_product_sets_data = []
  for sp_product_set in sp_product_sets["value"]:
      sp_product_set_data = {
        "ps_id": sp_product_set['fields']['ProductSetID'],
        "name": sp_product_set['fields']['ProductSet'],
        "lead_developer": "", # This field is not in the SharePoint list
        "updated_by_id": None
      }
      sp_product_sets_data.append(sp_product_set_data)
  # Create a dictionary for quick lookup of sc_product_set_data by t_id
  sc_product_sets_dict = {product_set['attributes']['ps_id']: product_set for product_set in sc_product_set_data}
  # Compare and update sp_product_set_data
  for sp_product_set in sp_product_sets_data:
    ps_id = sp_product_set['ps_id']
    if ps_id in sc_product_sets_dict:
      sc_product_set = sc_product_sets_dict[ps_id]
      if sp_product_set['name'].strip() != sc_product_set['attributes']['name'].strip():
        log.info(f"SC Updating product set name for ps_id {ps_id} from {sc_product_set['attributes']['name']} to {sp_product_set['name']}")
        sc.update('product-sets', sc_product_set['id'], {"name": sp_product_set['name']})
      # if sp_product_set['lead_developer'].strip() != sc_product_set['attributes']['lead_developer'].strip():
      #   log.info(f"SC Updating product set lead_developer for ps_id {ps_id} from {sc_product_set['attributes']['lead_developer']} to {sp_product_set['lead_developer']}")
      #   sc.update('product-sets', sc_product_set['id'], {"lead_developer": sp_product_set['lead_developer']})
    else:
      log.info(f"Adding product set {sp_product_set['name']} to Service Catalogue")
      sc.add('product-sets', sp_product_set)
    