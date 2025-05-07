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
    not_decommisioned = True
    if 'DecommissionedProduct' in sp_product['fields']:
      if sp_product['fields']['DecommissionedProduct'] == "Yes":
        not_decommisioned = False
      else:
        not_decommisioned = True
      
    if not_decommisioned:
      parent = None
      team = None
      product_set = None
      service_area = None
      subproductBool = False
      delivery_manager = None
      product_manager = None
      lead_developer = None
      if not re.match(r'^.+$', sp_product['fields']['Product']):
          return "Invalid name"
      if not re.match(r'^[A-Z]{3,4}[0-9]{0,5}$', sp_product['fields']['ProductID']):
          return "Invalid productId"
      if 'ProductType' in sp_product['fields']:
        subproductBool = True if sp_product['fields']['ProductType'] == "Subproduct" else False
      if 'ParentProductLookupId' in sp_product['fields']:
        parent_id = sp_product['fields']['ParentProductLookupId']
        try:
          parent = sp_product_dict[parent_id]['fields']['Product']
        except KeyError:
          parent = None
      if 'TeamLookupId' in sp_product['fields']:
        team_id = sp_product['fields']['TeamLookupId']
        try:
          team = sp_teams_dict[team_id]['fields']['Team']
        except KeyError:
          team = None
      if 'ProductSetLookupId' in sp_product['fields']:
        product_set_id = sp_product['fields']['ProductSetLookupId']
        try:
          product_set = sp_product_set_dict[product_set_id]['fields']['ProductSet']
        except KeyError:
          product_set = None        
      if 'ServiceAreaLookupId' in sp_product['fields']:
        service_area_id = sp_product['fields']['ServiceAreaLookupId']
        try:
          service_area = sp_service_area_dict[service_area_id]['fields']['ServiceArea']
        except KeyError:
          service_area = None
      if 'DeliveryManagerLookupId' in sp_product['fields']:
        delivery_manager_id = sp_product['fields']['DeliveryManagerLookupId']
        try:
          delivery_manager = sp_delivery_manager_dict[delivery_manager_id]['fields']['DeliveryManagerName']
        except KeyError:
          delivery_manager = None
      if 'ProductManagerLookupId' in sp_product['fields']:
        product_manager_id = sp_product['fields']['ProductManagerLookupId']
        try:
          product_manager = sp_product_manager_dict[product_manager_id]['fields']['ProductManagerName']
        except KeyError:
          product_manager = None
      if 'LeadDeveloperLookupId' in sp_product['fields']:
        lead_developer_id = sp_product['fields']['LeadDeveloperLookupId']
        try:
          lead_developer = sp_lead_developer_dict[lead_developer_id]['fields']['Title']
        except KeyError:
          lead_developer = None

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
        "updated_by_id": 33
      }

      if 'SlackchannelID' in sp_product['fields'] and sp_product['fields']['SlackchannelID'] is not None:
        sp_product_data["slack_channel_id"] = sp_product['fields']['SlackchannelID']

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
    