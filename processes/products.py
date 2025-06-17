import os
import re
from time import sleep
import html
from classes.slack import Slack
from classes.service_catalogue import ServiceCatalogue
from classes.sharepoint import SharePoint
from utilities.discovery import job

log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()

class Services:
  def __init__(self, sc_params, slack_params, log):
    self.sc = ServiceCatalogue(sc_params, log)
    self.sp = SharePoint(sp_params, log)
    self.slack = Slack(slack_params, log)
    self.log = log

def clean_value(value):
  if value is None:
    return None
  if isinstance(value, str):
    return html.unescape(value).strip()  # Decode HTML entities and strip whitespace
  return value

def fetchID(services, sp_product, dict, key):
  log = services.log
  if key in sp_product and sp_product[key] is not None:
    parent_key = sp_product[key]
    if parent_key in dict:
      sp_product[key] = dict[parent_key]['id']
    else:
      log.error(f"Product reference key not found for {key} in Service Catalogue :: {sp_product[key]}")
      del sp_product[key]
  return sp_product
   
def process_sc_products(services, max_threads=10):
  sc = services.sc
  sp = services.sp
  log = services.log
  
  sc_products_data = sc.get_all_records(sc.products_get)
  if not sc_products_data:
    job.error_messages.append(f'Errors occurred while fetching products from Service Catalogue')
  else:
    log.info(f'Found {len(sc_products_data)} Products in Service Catalogue before processing')
  sp_products = sp.get_sharepoint_lists(services, 'Products and Teams Main List')
  log.info(f"Found {len(sp_products['value'])} Products in SharePoint...")
  sc_teams_data = sc.get_all_records(sc.teams_get)
  sc_product_sets_data = sc.get_all_records(sc.product_sets_get)
  sc_service_areas_data = sc.get_all_records(sc.service_areas_get)

  # Lookup data for Teams, Product Set, Service Areas, Delivery Managers, Product Managers, Lead Developers
  sp_teams_data = sp.get_sharepoint_lists(services, 'Teams')
  sp_product_set_data = sp.get_sharepoint_lists(services, 'Product Set')
  sp_service_area_data = sp.get_sharepoint_lists(services, 'Service Areas')
  sp_delivery_manager_data = sp.get_sharepoint_lists(services, 'Delivery Managers')
  sp_product_manager_data = sp.get_sharepoint_lists(services, 'Product Managers')
  sp_lead_developer_data = sp.get_sharepoint_lists(services, 'Lead Developers')

  # Create a dictionary for Sharepoint data for Teams, Product Set, Service Areas, Delivery Managers, Product Managers, Lead Developers
  sp_teams_dict = {team['id']: team for team in sp_teams_data['value']}
  sp_product_set_dict = {product_set['id']: product_set for product_set in sp_product_set_data['value']}
  sp_service_area_dict = {service_area['id']: service_area for service_area in sp_service_area_data['value']}
  sp_product_dict = {product['id']: product for product in sp_products['value']}
  sp_delivery_manager_dict = {delivery_manager['id']: delivery_manager for delivery_manager in sp_delivery_manager_data['value']}
  sp_product_manager_dict = {product_manager['id']: product_manager for product_manager in sp_product_manager_data['value']}
  sp_lead_developer_dict = {lead_developer['id']: lead_developer for lead_developer in sp_lead_developer_data['value']}

  # Create a dictionary for quick lookup of service catalogue data 
  sc_products_dict = {product['attributes']['p_id'].strip(): product for product in sc_products_data}
  sc_product_name_dict = {product['attributes']['name'].strip(): product for product in sc_products_data}
  sc_team_name_dict = {team['attributes']['name'].strip(): team for team in sc_teams_data}
  sc_product_set_name_dict = {product_set['attributes']['name'].strip(): product_set for product_set in sc_product_sets_data}
  sc_service_area_name_dict = {service_area['attributes']['name'].strip(): service_area for service_area in sc_service_areas_data}

  sp_products_data = []
  parent = None
  team = None
  product_set = None
  service_area = None
  delivery_manager = None
  product_manager = None
  lead_developer = None
  for sp_product in sp_products["value"]:
    if 'DecommissionedProduct' in sp_product['fields'] and sp_product.get('fields').get('DecommissionedProduct').upper() == 'YES':
      not_decommisioned = False
    else:
      not_decommisioned = True

    if not_decommisioned:
      product_id=sp_product['fields']['ProductID'].strip()
      parent = None
      team = None
      product_set = None
      service_area = None
      subproductBool = False
      delivery_manager = None
      product_manager = None
      lead_developer = None
      if not re.match(r'^.+$', sp_product['fields']['Product']):
        log.error(f"Invalid name format for product_id: {product_id}")

      if not re.match(r'^[A-Z]{3,4}[0-9]{0,5}$', sp_product['fields']['ProductID']):
        log.error(f"Invalid productId format for product_id: {product_id}")

      if 'ProductType' in sp_product['fields']:
        subproductBool = True if sp_product['fields']['ProductType'] == "Subproduct" else False
      else:
        log.debug(f"Product Type not found for product_id: {product_id}")
        subproductBool = False

      if 'ParentProductLookupId' in sp_product['fields']:
        parent_id = sp_product['fields']['ParentProductLookupId']
        parent = sp_product_dict.get(parent_id, {}).get('fields', {}).get('Product')
        if not parent:
          log.debug(f"Parent product not found for product_id: {product_id}")

      if 'TeamLookupId' in sp_product['fields']:
        team_id = sp_product['fields']['TeamLookupId']
        team = sp_teams_dict.get(team_id, {}).get('fields', {}).get('Team')
        if not team:
          log.debug(f"Team not found for product_id: {product_id}")

      if 'ProductSetLookupId' in sp_product['fields']:
        product_set_id = sp_product['fields']['ProductSetLookupId']
        product_set = sp_product_set_dict.get(product_set_id, {}).get('fields', {}).get('ProductSet')
        if not product_set:
          log.debug(f"Product Set not found for product_id: {product_id}")

      if 'ServiceAreaLookupId' in sp_product['fields']:
        service_area_id = sp_product['fields']['ServiceAreaLookupId']
        service_area = sp_service_area_dict.get(service_area_id, {}).get('fields', {}).get('ServiceArea')
        if not service_area:
          log.debug(f"Service Area not found for product_id: {product_id}")

      if 'DeliveryManagerLookupId' in sp_product['fields']:
        delivery_manager_id = sp_product['fields']['DeliveryManagerLookupId']
        delivery_manager = sp_delivery_manager_dict.get(delivery_manager_id, {}).get('fields', {}).get('DeliveryManagerName')
        if not delivery_manager:
          log.debug(f"Delivery Manager not found for product_id: {product_id}")

      if 'ProductManagerLookupId' in sp_product['fields']:
        product_manager_id = sp_product['fields']['ProductManagerLookupId']
        product_manager = sp_product_manager_dict.get(product_manager_id, {}).get('fields', {}).get('ProductManagerName')
        if not product_manager:
          log.debug(f"Product Manager not found for product_id: {product_id}")

      if 'LeadDeveloperLookupId' in sp_product['fields']:
        lead_developer_id = sp_product['fields']['LeadDeveloperLookupId']
        lead_developer = sp_lead_developer_dict.get(lead_developer_id, {}).get('fields', {}).get('Title')
        if not lead_developer:
          log.debug(f"Lead Developer not found for product_id: {product_id}")

      sp_product_data = {
        "p_id": sp_product['fields']['ProductID'].strip(),
        "name": clean_value(sp_product['fields']['Product']),
        "subproduct": subproductBool,
        "parent": parent,
        "description": clean_value(sp_product['fields']['Description_x0028_SourceData_x00']) if 'Description_x0028_SourceData_x00' in sp_product['fields'] else None,
        "team": team,
        "phase": sp_product['fields']['field_7'] if 'field_7' in sp_product['fields'] else None,
        "product_set": product_set,
        "service_area": service_area,
        "delivery_manager": delivery_manager,
        "product_manager": product_manager,
        "lead_developer": lead_developer,
        "updated_by_id": 34
      }

      if slack_channel_id := sp_product.get('fields', {}).get('SlackchannelID'):
          sp_product_data["slack_channel_id"] = slack_channel_id

      sp_products_data.append(sp_product_data)

  sp_products_dict = {product['p_id']: product for product in sp_products_data}
  # Compare and update sp_product_data
  change_count = 0 
  log_messages = []
  log_messages.append("************** Processing Products *********************")
  for sp_product in sp_products_data:
    p_id = sp_product['p_id']
    if p_id in sc_products_dict:
      sc_product = sc_products_dict[p_id]
      mismatch_flag = False
      for key in list(sp_product.keys()):
        compare_flag=False
        if key in sp_product and key in sc_product['attributes']:
          compare_flag=True
        if compare_flag and key!='updated_by_id' and key!='subproduct' and key!="p_id":
          sp_value = clean_value(sp_product[key])
          if key == 'parent' or key == 'team' or key == 'product_set' or key == 'service_area':
            if sc_product['attributes'][key].get('data') and sc_product['attributes'][key]['data'].get('attributes'):
              sc_value = clean_value(sc_product['attributes'][key]['data']['attributes']['name'])
            else:
              sc_value = None
          else:
            sc_value=clean_value(sc_product['attributes'][key])

          if sp_value is not None:
            if (sp_value or "").strip() != (sc_value or "").strip():
              log_messages.append(f"SC Updating Products p_id {p_id}({key}) :: {sc_value} -> {sp_value}")
              log.info(f"SC Updating Products p_id {p_id}({key}) :: {sc_value} -> {sp_value}")
              mismatch_flag = True
            else:
              del sp_product[key]
          
        elif compare_flag and key=='subproduct':
          if sp_product[key] != sc_product['attributes'][key]:
            log_messages.append(f"Updating Products p_id {p_id}({key}) :: {sp_value} -> {sc_value}")
            mismatch_flag = True
          else:
            del sp_product[key]

      if mismatch_flag:
        sp_product = fetchID(services, sp_product, sc_product_name_dict, "parent") if 'parent' in sp_product else sp_product
        sp_product = fetchID(services, sp_product, sc_team_name_dict, "team") if 'team' in sp_product else sp_product
        sp_product = fetchID(services, sp_product, sc_product_set_name_dict, "product_set") if 'product_set' in sp_product else sp_product
        sp_product = fetchID(services, sp_product, sc_service_area_name_dict, "service_area") if 'service_area' in sp_product else sp_product
        log.info(f"Updating Product :: p_id {p_id} :: {sc_product} -> {sp_product}")
        sc.update('products', sc_product['id'], sp_product)
        change_count += 1
    else:
      sp_product = fetchID(services, sp_product, sc_product_name_dict, "parent")
      sp_product = fetchID(services, sp_product, sc_team_name_dict, "team")
      sp_product = fetchID(services, sp_product, sc_product_set_name_dict, "product_set")
      sp_product = fetchID(services, sp_product, sc_service_area_name_dict, "service_area")
      log_messages.append(f"Adding Product :: sp_product")
      log.info(f"Adding Product :: {sp_product}")
      sc.add('products', sp_product)
      change_count += 1

  for sc_product in sc_products_data:
    p_id = sc_product['attributes']['p_id'].strip()
    if p_id not in sp_products_dict and 'HMPPS' not in p_id and 'DPS999' not in p_id:
      log_messages.append(f"Unpublishing product :: {sc_product['attributes']['p_id']}")
      log.info(f"Unpublishing product  :: {sc_product['attributes']['p_id']}")
      sc.unpublish('products', sc_product['id'])
      change_count += 1

  log_messages.append(f"Products processed {change_count} in Service Catalogue") 
  log.info(f"Products processed {change_count} in Service Catalogue")
  log_messages.append("*******************************************************")
  return log_messages
    