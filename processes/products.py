import os
import re
import html
from hmpps.services.job_log_handling import (
  log_debug,
  log_error,
  log_info,
)

log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()


def clean_value(value):
  if value is None:
    return None
  if isinstance(value, str):
    return html.unescape(value).strip()  # Decode HTML entities and strip whitespace
  return value


def fetchID(sp_product, dict, key):
  if key in sp_product and sp_product[key] is not None:
    parent_key = sp_product[key]
    if parent_key in dict:
      sp_product[key] = dict[parent_key]['documentId']
    else:
      log_error(
        f'Product reference key not found for {key} in Service Catalogue :: {sp_product[key]}'
      )
      del sp_product[key]
  return sp_product


# generic lookup
def link_product_data(sp, sp_product):
  log_debug('Linking product with other Sharepoint data')
  product_id = sp_product.get('fields', {}).get('ProductID', None)
  product_data = {}
  # This is a tuple of
  # dictionary_key,lookup_key,sharepoint_list,field_to_return
  fields = [
    ('parent', 'ParentProductLookupId', 'Products and Teams Main List', 'Product'),
    ('team', 'TeamLookupId', 'Teams', 'Team'),
    ('product_set', 'ProductSetLookupId', 'Product Set', 'ProductSet'),
    ('service_area', 'ServiceAreaLookupId', 'Service Areas', 'ServiceArea'),
    (
      'delivery_manager',
      'DeliveryManagerLookupId',
      'Delivery Managers',
      'DeliveryManagerName',
    ),
    (
      'product_manager',
      'ProductManagerLookupId',
      'Product Managers',
      'ProductManagerName',
    ),
    ('lead_developer', 'LeadDeveloperLookupId', 'Lead Developers', 'Title'),
  ]
  for field in fields:
    if field_id := sp_product.get('fields', {}).get(field[1]):
      product_data[field[0]] = (
        sp.dict[field[2]].get(field_id, {}).get('fields', {}).get(field[3], None)
      )
      if not product_data[field[0]]:
        log_error(
          f'{field[0]} matching {field[1]} not found for product_id: {product_id}'
        )
  return product_data


def extract_sp_products_data(sp):
  sp_products_data = []
  for sp_product in sp.data['Products and Teams Main List'].get('value'):
    log_debug(
      f'Extracting SharePoint product data for: {sp_product.get("fields", {}).get("ProductID", None)}'
    )
    if sp_product.get('fields').get('DecommissionedProduct', '').upper() == 'YES':
      # Skip the processing if it's decommissioned
      log_info(
        f'Skipping {sp_product.get("fields", {}).get("ProductID", None)} (decommissioned) ...'
      )
      continue

    product_id = sp_product.get('fields', {}).get('ProductID', None)
    if product_id:
      if not re.match(r'^.+$', sp_product.get('fields', {}).get('Product')):
        log_error(f'Invalid name format for product_id: {product_id}')

      if not re.match(
        r'^[A-Z]{3,4}[0-9]{0,5}$', sp_product.get('fields', {}).get('ProductID')
      ):
        log_error(f'Invalid productId format for product_id: {product_id}')

      # set subproductBool directly from the comparison
      subproductBool = (
        str(sp_product.get('fields', {}).get('ProductType', '')).strip().lower()
        == 'subproduct'
      )

      # fetch links to other Sharepoint lists
      linked_product_data = link_product_data(sp, sp_product)

      sp_product_data = {
        'p_id': product_id,
        'name': clean_value(sp_product.get('fields', {}).get('Product', None)),
        'subproduct': subproductBool,
        'description': clean_value(
          sp_product['fields'].get('Description_x0028_SourceData_x00', None)
        ),
        'phase': sp_product.get('fields', {}).get('field_7', None),
        'slack_channel_id': sp_product.get('fields', {}).get('SlackchannelID', None),
        # "updated_by_id": 34
      }
      # add the fetched data
      sp_product_data.update(linked_product_data)
      sp_products_data.append(sp_product_data)
  return sp_products_data


def process_sc_products(services):
  def log_and_append(message):
    log_info(message)
    log_messages.append(message)

  sc = services.sc
  sp = services.sp

  # Service Catalogue
  log_info('Processing Products ')

  log_debug(
    'Fetching Products, Teams, Products Sets, Service Areas from Service Catalogue'
  )
  sc_products_data = sc.get_all_records(sc.products_get)
  sc_teams_data = sc.get_all_records('teams')
  sc_product_sets_data = sc.get_all_records('product-sets')
  sc_service_areas_data = sc.get_all_records('service-areas')

  # Create the dictionaries
  sc_products_dict = {
    product.get('p_id').strip(): product for product in sc_products_data
  }
  sc_product_name_dict = {
    product.get('name').strip(): product for product in sc_products_data
  }
  sc_team_name_dict = {team.get('name').strip(): team for team in sc_teams_data}
  sc_product_set_name_dict = {
    product_set.get('name').strip(): product_set for product_set in sc_product_sets_data
  }
  sc_service_area_name_dict = {
    service_area.get('name').strip(): service_area
    for service_area in sc_service_areas_data
  }

  # Sharepoint data processing
  sp_products_data = extract_sp_products_data(sp)

  sp_products_dict = {product.get('p_id'): product for product in sp_products_data}

  # Quick summary before we start
  log_info(f'Found {len(sp_products_data)} products in SharePoint (after processing)')
  log_info(f'Found {len(sc_products_data)} products in Service Catalogue')

  # Compare and update sp_product_data
  log_info('Processing prepared products sharepoint data for service catalogue ')
  change_count = 0
  log_messages = []
  log_messages.append('************** Processing Products *********************')
  for sp_product in sp_products_data:
    p_id = sp_product.get('p_id')
    log_debug(f'Comparing Product p_id {p_id} :: {sp_product}')
    if p_id in sc_products_dict:
      try:
        sc_product = sc_products_dict.get(p_id, {})
        mismatch_flag = False
        for key in list(sp_product.keys()):
          sp_value = clean_value(sp_product.get(key))
          sc_value = None
          compare_flag = False
          if key in sp_product and key in sc_product:
            compare_flag = True
          if (
            compare_flag
            and key != 'updated_by_id'
            and key != 'subproduct'
            and key != 'p_id'
          ):
            if (
              key == 'parent'
              or key == 'team'
              or key == 'product_set'
              or key == 'service_area'
            ):
              if sc_product.get(key):
                try:
                  sc_value = clean_value(sc_product.get(key).get('name'))
                except KeyError:
                  log_error(
                    f'Key {key} not found in Service Catalogue data for p_id {p_id}'
                  )
            else:
              try:
                sc_value = clean_value(sc_product.get(key))
              except KeyError:
                log_error(
                  f'Key {key} not found in Service Catalogue data for p_id {p_id}'
                )

            if sp_value is not None:
              if (sp_value or '').strip() != (sc_value or '').strip():
                log_messages.append(
                  f'SC Updating Products p_id {p_id}({key}) :: {sc_value} -> {sp_value}'
                )
                log_info(
                  f'SC Updating Products p_id {p_id}({key}) :: {sc_value} -> {sp_value}'
                )
                mismatch_flag = True
              else:
                del sp_product[key]

          elif compare_flag and key == 'subproduct':
            if sp_product.get(key) != sc_product.get(key):
              log_messages.append(
                f'Updating Products p_id {p_id}({key}) :: {sp_value} -> {sc_value}'
              )
              mismatch_flag = True
            else:
              del sp_product[key]

        if mismatch_flag:
          sp_product = (
            fetchID(sp_product, sc_product_name_dict, 'parent')
            if 'parent' in sp_product
            else sp_product
          )
          sp_product = (
            fetchID(sp_product, sc_team_name_dict, 'team')
            if 'team' in sp_product
            else sp_product
          )
          sp_product = (
            fetchID(sp_product, sc_product_set_name_dict, 'product_set')
            if 'product_set' in sp_product
            else sp_product
          )
          sp_product = (
            fetchID(sp_product, sc_service_area_name_dict, 'service_area')
            if 'service_area' in sp_product
            else sp_product
          )
          log_info(f'Updating Product :: p_id {p_id} :: {sc_product} -> {sp_product}')
          sc.update('products', sc_product.get('documentId'), sp_product)
          change_count += 1
      except Exception as e:
        log_error(f'Error processing product p_id {p_id}: {e}')
    else:
      sp_product = fetchID(sp_product, sc_product_name_dict, 'parent')
      sp_product = fetchID(sp_product, sc_team_name_dict, 'team')
      sp_product = fetchID(sp_product, sc_product_set_name_dict, 'product_set')
      sp_product = fetchID(sp_product, sc_service_area_name_dict, 'service_area')
      log_and_append(f'Adding Product :: {sp_product}')
      sc.add('products', sp_product)
      change_count += 1

  for sc_product in sc_products_data:
    p_id = sc_product.get('p_id').strip()
    if p_id not in sp_products_dict and 'HMPPS' not in p_id and 'DPS999' not in p_id:
      log_messages.append(f'Deleting product :: {sc_product.get("p_id")}')
      log_info(f'Deleting product  :: {sc_product.get("p_id")}')
      sc.delete('products', sc_product.get('documentId'))
      change_count += 1

  log_and_append(f'Products in Service Catalogue processed: {change_count}')
  log_messages.append('*******************************************************')
  return log_messages
