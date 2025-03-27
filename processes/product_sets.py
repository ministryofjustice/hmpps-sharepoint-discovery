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

  sc_product_sets_data = sc.get_all_records(sc.product_sets_get)
  log.info(f'Found {len(sc_product_sets_data)} product sets in Service Catalogue before processing')
  sp_product_sets = sp.get_sharepoint_lists('Product Set')
  sp_lead_developer_data = sp.get_sharepoint_lists('Lead Developers')
  sp_lead_developer_dict = {lead_developer['id']: lead_developer for lead_developer in sp_lead_developer_data['value']}
  log.info(f'Found {len(sp_product_sets["value"])} product sets in SharePoint...')
  sp_product_sets_data = []
  for sp_product_set in sp_product_sets["value"]:
    if 'LeadDeveloperLookupId' in sp_product_set['fields']:
      lead_developer_id = sp_product_set['fields']['LeadDeveloperLookupId']
      try:
        lead_developer = sp_lead_developer_dict[lead_developer_id]['fields']['Title']
      except KeyError:
        lead_developer = None

    sp_product_set_data = {
      "ps_id": sp_product_set['fields']['ProductSetID'],
      "name": sp_product_set['fields']['ProductSet'],
      "lead_developer": lead_developer,
      "updated_by_id": 33
    }
    sp_product_sets_data.append(sp_product_set_data)
  # Create a dictionary for quick lookup of sc_product_sets_data by t_id
  sc_product_sets_dict = {product_set['attributes']['ps_id']: product_set for product_set in sc_product_sets_data}
  sp_product_sets_dict = {product_set['ps_id']: product_set for product_set in sp_product_sets_data}

  # Compare and update sp_product_set_data
  change_count = 0
  log_messages = []
  log_messages.append("************** Processing Product Sets *********************")
  for sp_product_set in sp_product_sets_data:
    ps_id = sp_product_set['ps_id']
    if ps_id in sc_product_sets_dict:
      sc_product_set = sc_product_sets_dict[ps_id]
      if sp_product_set['name'].strip() != sc_product_set['attributes']['name'].strip():
        log_messages.append(f"Updating product set :: ps_id {ps_id} :: {sc_product_set} -> {sp_product_set}")
        log.info(f"Updating product set :: ps_id {ps_id} :: {sc_product_set['attributes']['name']} to {sp_product_set['name']}")
        sc.update('product-sets', sc_product_set['id'], sp_product_set)
        change_count += 1
    else:
      log_messages.append(f"Adding product set :: {sp_product_set['name']}")
      log.info(f"Adding product set {sp_product_set}") 
      sc.add('product-sets', sp_product_set)
      change_count += 1

  for sc_product_set in sc_product_sets_data:
    ps_id = sc_product_set['attributes']['ps_id']
    if ps_id not in sp_product_sets_dict:
      log_messages.append(f"Unpublishing product set :: {sc_product_set}")
      log.info(f"Unpublishing product set :: {sc_product_set}")
      sc.unpublish('product-sets', sc_product_set['id'])
      change_count += 1

  log_messages.append(f"Product Set changed {change_count} in Service Catalogue") 
  log.info(f"Product Set changed {change_count} in Service Catalogue")
  return log_messages