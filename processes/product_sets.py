import os
from time import sleep
from classes.slack import Slack
from classes.service_catalogue import ServiceCatalogue
from classes.sharepoint import SharePoint
from slugify import slugify
from utilities.job_log_handling import log_debug, log_error, log_info, log_critical

class Services:
  def __init__(self, sc_params, slack_params):
    self.sc = ServiceCatalogue(sc_params)
    self.sp = SharePoint(sp_params)
    self.slack = Slack(slack_params)

def process_sc_product_sets(services, max_threads=10):
  sc = services.sc
  sp = services.sp

  log_info('Processing Product Sets ')
  try:
    log_info('Fetching product sets from Service Catalogue')
    sc_product_sets_data = sc.get_all_records(sc.product_sets_get)
    log_info(f'Found {len(sc_product_sets_data)} product sets in Service Catalogue')
  except Exception as e:
    log_error(f'Error fetching product sets from Service Catalogue: {e}, discontinuing processing product_sets.py')
    return None
  
  try:
    log_info('Fetching product sets from SharePoint')
    sp_product_sets = sp.get_sharepoint_lists(services, 'Product Set')
    log_info(f'Found {len(sp_product_sets.get('value'))} product sets in SharePoint')
  except Exception as e:
    log_error(f'Error fetching SharePoint product sets: {e}, discontinuing processing product_sets.py')
    return None

  try:
    log_info('Fetching lead developers from SharePoint')
    sp_lead_developer_data = sp.get_sharepoint_lists(services, 'Lead Developers')
  except Exception as e:
    log_error(f'Error fetching SharePoint lead developers: {e}')
    return None
  
  try:
    log_info('Creating Lookup dictionaries ')
    sp_lead_developer_dict = {lead_developer.get('id'): lead_developer for lead_developer in sp_lead_developer_data.get('value')}
    sc_product_sets_dict = {product_set.get('ps_id'): product_set for product_set in sc_product_sets_data}
    log_info('Lookup dictionaries created successfully.')
  except Exception as e:
    log_error(f'Error creating lookup dictionaries: {e}')
    return None

  log_info('Preparing SharePoint product sets data for processing')
  sp_product_sets_data = []
  for sp_product_set in sp_product_sets.get('value'):
    if product_set_id := sp_product_set.get('fields').get('ProductSetID', None):
      if lead_developer_id := sp_product_set.get('fields').get('LeadDeveloperLookupId'):
        try:
          lead_developer = sp_lead_developer_dict.get(lead_developer_id).get('fields').get('Title')
        except KeyError:
          lead_developer = None
          log_error(f'Lead Developer ID {lead_developer_id} not found in SharePoint lead developers data.')

      product_set_name = sp_product_set.get('fields').get('ProductSet', None)
      sp_product_set_data = {
        "ps_id": product_set_id,
        "name": product_set_name,
        "lead_developer": lead_developer,
        "slug": slugify(product_set_name) if product_set_name else None,
        # "updated_by_id": 34
      }
      sp_product_sets_data.append(sp_product_set_data)
  log_info('SharePoint product sets prepared successfully for Service Catalogue processing.')

  try:
    log_debug('Creating SharePoint product sets dictionary')
    sp_product_sets_dict = {product_set.get('ps_id'): product_set for product_set in sp_product_sets_data}
  except Exception as e:
    log_error(f'Error creating SharePoint product sets dictionary: {e}')
    return None

  # Compare and update sp_product_set_data
  log_info('Comparing and updating product sets in service catalogue')
  change_count = 0
  log_messages = []
  log_info("Processing prepared product set sharepoint data for service catalogue ")
  log_messages.append("************** Processing Product Sets *********************")
  for sp_product_set in sp_product_sets_data:
    ps_id = sp_product_set.get('ps_id')
    log_info(f"Comparing product set {ps_id}")
    try:
      if ps_id in sc_product_sets_dict:
        sc_product_set = sc_product_sets_dict.get(ps_id)
        if sp_product_set.get('name').strip() != sc_product_set.get('name').strip() or sp_product_set.get('slug') != sc_product_set.get('slug') or sp_product_set.get('lead_developer') != sc_product_set.get('lead_developer'):
          log_messages.append(f"Updating product set :: ps_id {ps_id} :: {sc_product_set} -> {sp_product_set}")
          log_info(f"Updating product set :: ps_id {ps_id} :: {sc_product_set.get('name')} to {sp_product_set.get('name')}")
          sc.update('product-sets', sc_product_set.get('documentId'), sp_product_set)
          change_count += 1
      else:
        log_messages.append(f"Adding product set :: {sp_product_set.get('name')}")
        log_info(f"Adding product set {sp_product_set}") 
        sc.add('product-sets', sp_product_set)
        change_count += 1
    except Exception as e:
      log_messages.append(f"Error processing product set {ps_id}: {e}")
      log_error(f"Error processing product set {ps_id}: {e}")

  for sc_product_set in sc_product_sets_data:
    ps_id = sc_product_set.get('ps_id')
    if ps_id not in sp_product_sets_dict:
      log_messages.append(f"Unpublishing product set :: {sc_product_set}")
      log_info(f"Unpublishing product set :: {sc_product_set}")
      try:
        sc.unpublish('product-sets', sc_product_set.get('documentId'))
      except Exception as e:
        log_error(f"Error unpublishing product set {ps_id}: {e}")
      change_count += 1

  log_messages.append(f"Product Set processed {change_count} in Service Catalogue") 
  log_info(f"Product Set processed {change_count} in Service Catalogue")
  return log_messages