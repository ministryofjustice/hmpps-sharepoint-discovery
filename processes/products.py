import os
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

def process_sc_products(services, max_threads=10):
  sc = services.sc
  sp = services.sp
  log = services.log

  sc_product_data = sc.get_all_records(sc.products_get)
  log.info(f'Found {len(sc_product_data)} Products in Service Catalogue before processing')
  sp_products = sp.get_sharepoint_lists('Products and Teams Main List','ProductID,Product')

  # Lookup data for Teams, Product Set and Service Area 
  sp_teams_data = sp.get_sharepoint_lists('Teams','TeamID,Team')
  sp_product_set_data = sp.get_sharepoint_lists('Product Set','ProductSetID,ProductSet')
  sp_service_area_data = sp.get_sharepoint_lists('Service Areas','ServiceAreaID,ServiceArea')

  # Lookup data for Delivery manager, Product manager and Lead developer
  sp_delivery_manager_data = sp.get_sharepoint_lists('Delivery Managers','DeliveryManagerLookupId,DeliveryManager')
  sp_product_manager_data = sp.get_sharepoint_lists('Product Managers','ProductManagerLookupId,ProductManager')
  sp_lead_developer_data = sp.get_sharepoint_lists('Lead Developers','LeadDeveloperLookupId,LeadDev')

  # Create a dictionary for quick lookup of sp_teams_data by TeamID
  sp_teams_dict = {team['id']: team for team in sp_teams_data['value']}
  sp_product_set_dict = {product_set['id']: product_set for product_set in sp_product_set_data['value']}
  sp_service_area_dict = {service_area['id']: service_area for service_area in sp_service_area_data['value']}
  sp_product_dict = {product['id']: product for product in sp_products['value']}
  sp_delivery_manager_dict = {delivery_manager['id']: delivery_manager for delivery_manager in sp_delivery_manager_data['value']}
  sp_product_manager_dict = {product_manager['id']: product_manager for product_manager in sp_product_manager_data['value']}
  sp_lead_developer_dict = {lead_developer['id']: lead_developer for lead_developer in sp_lead_developer_data['value']}
  sp_products_data = []
  parent = None
  team = None
  product_set = None
  service_area = None
  delivery_manager = None
  product_manager = None
  lead_developer = None
  for sp_product in sp_products["value"]:
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
      "p_id": sp_product['fields']['ProductID'],
      "name": sp_product['fields']['Product'],
      "subproduct": subproductBool,
      "parent": parent,
      # "legacy": legacyBool,
      "description": sp_product['fields']['Description_x0028_SourceData_x00'] if 'Description_x0028_SourceData_x00' in sp_product['fields'] else None,
      "team": team,
      "phase": sp_product['fields']['field_7'] if 'field_7' in sp_product['fields'] else None,
      "product_set": product_set,
      "service_area": service_area,
      "delivery_manager": delivery_manager,
      "product_manager": product_manager,
      "lead_developer": lead_developer,
      # "confluence_link": confluenceLink,
      # "gdrive_link": item.properties['gDriveLink'],
      "updated_by_id": None
    }
    if 'slackChannelId' in sp_product['fields'] and sp_product['fields']['slackChannelId'] is not None:
      sp_product_data["slack_channel_id"] = sp_product['fields']['slackChannelId']
    sp_products_data.append(sp_product_data)
  # Create a dictionary for quick lookup of sc_product_data by t_id
  sc_products_dict = {product['attributes']['p_id']: product for product in sc_product_data}
  # Compare and update sp_product_data
  for sp_product in sp_products_data:
    p_id = sp_product['p_id']
    if p_id in sc_products_dict:
      sc_product = sc_products_dict[p_id]
      mismatch_flag = False
      for key in sp_product.keys():
        compare_flag=False
        if key in sp_product and key in sc_product['attributes']:
          compare_flag=True
        if compare_flag and key!='updated_by_id' and key!='subproduct':
          sp_value = sp_product[key]
          sc_value = sc_product['attributes'][key]
          if sp_value is not None and sc_value is not None:
            if sp_value.strip() != sc_value.strip():
              mismatch_flag = True
            # else:
            #   print(f"Values are same for {key} {sp_value} {sc_value}")
        elif compare_flag and key=='subproduct':
          if sp_product[key] != sc_product['attributes'][key]:
            mismatch_flag = True
      if mismatch_flag:
        log.info(f"SC Updating Products for sa_id {p_id} from {sc_product['attributes']} to **** {sp_product}")
        log.info("--------------------")
    else:
      log.info(f"Adding Product {sp_product['p_id']} {sp_product['name']} to Service Catalogue")
      log.info("--------------------")
      # sc.add('service-areas', sp_product)
    