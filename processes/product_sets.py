from hmpps.services.job_log_handling import log_warning, log_error, log_info, log_debug
import json


def find_lead_developer(sp_product_set, sp_lead_developer_dict):
  if lead_developer_id := sp_product_set.get('fields').get('LeadDeveloperLookupId'):
    return (
      sp_lead_developer_dict.get(lead_developer_id, {}).get('fields', {}).get('Title')
    ) or None
  else:
    log_warning(
      f'Lead Developer ID {lead_developer_id} not found in SharePoint lead developers data.'
    )
  return None


def fetch_sp_product_sets_data(sp):
  sp_product_sets_data = []
  for sp_product_set in sp.data['Product Set'].get('value'):
    if product_set_id := sp_product_set.get('fields', {}).get('ProductSetID', None):
      lead_developer = find_lead_developer(sp_product_set, sp.dict['Lead Developers'])
      sp_product_set_data = {
        'ps_id': product_set_id,
        'name': sp_product_set.get('fields').get('ProductSet', None),
        'lead_developer': lead_developer,
        # "updated_by_id": 34
      }
      sp_product_sets_data.append(sp_product_set_data)
  log_debug(f'sp_product_sets_data is:\n{json.dumps(sp_product_sets_data, indent=2)}')
  return sp_product_sets_data


def process_sc_product_sets(services):
  def log_and_append(message):
    log_info(message)
    log_messages.append(message)

  sc = services.sc
  sp = services.sp

  log_info('Processing Product Sets')

  # Fetch the data from Service Catalogue
  sc_product_sets_data = sc.get_all_records('product-sets')
  if not sc_product_sets_data:
    log_warning('No product sets returned from the Service Catalogue')

  log_info(f'Found {len(sc_product_sets_data)} product sets in Service Catalogue')

  # Create dictionary of product sets
  sc_product_sets_dict = {
    product_set.get('ps_id'): product_set for product_set in sc_product_sets_data
  }

  # Prepare Sharepoint Product Set data for processing
  sp_product_sets_data = fetch_sp_product_sets_data(sp)

  sp_product_sets_dict = {
    product_set.get('ps_id'): product_set for product_set in sp_product_sets_data
  }

  # Compare and update sp_product_set_data
  log_info('Comparing and updating product sets in service catalogue')
  change_count = 0
  log_messages = []

  log_and_append('************** Processing Product Sets *********************')
  for sp_product_set in sp_product_sets_data:
    ps_id = sp_product_set.get('ps_id')
    log_info(f'Comparing product set {ps_id}')
    if ps_id not in sc_product_sets_dict:
      log_and_append(f'Adding product set :: {sp_product_set.get("name")}')
      sc.add('product-sets', sp_product_set)
      change_count += 1
      continue

    sc_product_set = sc_product_sets_dict.get(ps_id, {})
    if sp_product_set.get('name', '').strip() != sc_product_set.get('name', '').strip():
      log_and_append(
        f'Updating product set :: ps_id {ps_id} :: {sc_product_set} -> {sp_product_set}'
      )
      sc.update('product-sets', sc_product_set.get('documentId'), sp_product_set)
      change_count += 1

  # Delete the product sets that no longer exist in Sharepoint
  for sc_product_set in sc_product_sets_data:
    if sc_product_set.get('ps_id') not in sp_product_sets_dict:
      log_and_append(f'Deleting product set :: {sc_product_set}')
      sc.delete('product-sets', sc_product_set.get('documentId'))
      change_count += 1

  log_and_append(f'Product Sets in Service Catalogue processed: {change_count}')
  return log_messages
