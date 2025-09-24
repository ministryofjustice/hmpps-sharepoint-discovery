import os
import re
from time import sleep
import html
from classes.slack import Slack
from classes.service_catalogue import ServiceCatalogue
from classes.sharepoint import SharePoint
from utilities.job_log_handling import log_debug, log_error, log_info, log_critical, log_warning

log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()

class Services:
  def __init__(self, sc_params, slack_params):
    self.sc = ServiceCatalogue(sc_params)
    self.sp = SharePoint(sp_params)
    self.slack = Slack(slack_params)

def clean_value(value):
  if value is None:
    return None
  if isinstance(value, str):
    return html.unescape(value).strip()  # Decode HTML entities and strip whitespace
  return value

def fetchID(services, sp_product, dict, key):
  if key in sp_product and sp_product[key] is not None:
    parent_key = sp_product[key]
    if parent_key in dict:
      sp_product[key] = dict[parent_key]['documentId']
    else:
      log_error(f"Product reference key not found for {key} in Service Catalogue :: {sp_product[key]}")
      del sp_product[key]
  return sp_product
   
def process_sc_products(services, max_threads=10):
  sc = services.sc
  sp = services.sp
  
  log_info('Processing Products ')
  try:
    log_info("Fetching products from Service Catalogue")
    sc_products_data = sc.get_all_records(sc.products_get)
    log_info(f'Found {len(sc_products_data)} Products in Service Catalogue before processing')
  except Exception as e:
    log_error(f'Error fetching products from Service Catalogue: {e}, discontinuing processing products.py.')
    return None
  
  try:
    log_debug("Fetching Products from SharePoint")
    sp_products = sp.get_sharepoint_lists(services, 'Products and Teams Main List')
    log_info(f"Found {len(sp_products.get('value'))} Products in SharePoint")
  except Exception as e:
    log_error(f'Error fetching SharePoint products: {e}, discontinuing processing products.py.')
    return None

  try:
    log_info("Fetching Teams, Products Sets, Service Areas from Service Catalogue")
    sc_teams_data = sc.get_all_records(sc.teams_get)
    sc_product_sets_data = sc.get_all_records(sc.product_sets_get)
    sc_service_areas_data = sc.get_all_records(sc.service_areas_get)
    log_info("Fetching Teams, Product Sets, Service Areas from Service Catalogue completed.")
  except Exception as e:
    log_error(f'Error fetching Teams, Product Sets, Service Areas from Service Catalogue: {e}, discontinuing processing products.py.')
    return None

  # Lookup data for Teams, Product Set, Service Areas, Delivery Managers, Product Managers, Lead Developers
  try:
    log_info("Fetching SharePoint Teams data ")
    sp_teams_data = sp.get_sharepoint_lists(services, 'Teams')
    log_info("Fetching SharePoint Product Set data ")
    sp_product_set_data = sp.get_sharepoint_lists(services, 'Product Set')
    log_info("Fetching SharePoint Service Area data ")
    sp_service_area_data = sp.get_sharepoint_lists(services, 'Service Areas')
    log_info("Fetching SharePoint Delivery Managers data ")
    sp_delivery_manager_data = sp.get_sharepoint_lists(services, 'Delivery Managers')
    log_info("Fetching SharePoint Product Managers data ")
    sp_product_manager_data = sp.get_sharepoint_lists(services, 'Product Managers')
    log_info("Fetching SharePoint Lead Developers data ")
    sp_lead_developer_data = sp.get_sharepoint_lists(services, 'Lead Developers')
  except Exception as e:
    log_error("Failed to fetch SharePoint data. Please check the SharePoint list names above, discontinuing processing products.py.")
    return None
  
  try:
    log_info("Creating SharePoint dictionaries for quick lookup")
    sp_teams_dict = {team.get('id'): team for team in sp_teams_data.get('value')}
    sp_product_set_dict = {product_set.get('id'): product_set for product_set in sp_product_set_data.get('value')}
    sp_service_area_dict = {service_area.get('id'): service_area for service_area in sp_service_area_data.get('value')}
    sp_product_dict = {product.get('id'): product for product in sp_products.get('value')}
    sp_delivery_manager_dict = {delivery_manager.get('id'): delivery_manager for delivery_manager in sp_delivery_manager_data.get('value')}
    sp_product_manager_dict = {product_manager.get('id'): product_manager for product_manager in sp_product_manager_data.get('value')}
    sp_lead_developer_dict = {lead_developer.get('id'): lead_developer for lead_developer in sp_lead_developer_data.get('value')}
    log_info("Creating SharePoint dictionaries for quick lookup completed")
    log_info("Creating Service Catalogue dictionaries for quick lookup")
    sc_products_dict = {product.get('p_id').strip(): product for product in sc_products_data}
    sc_product_name_dict = {product.get('name').strip(): product for product in sc_products_data}
    sc_team_name_dict = {team.get('name').strip(): team for team in sc_teams_data}
    sc_product_set_name_dict = {product_set.get('name').strip(): product_set for product_set in sc_product_sets_data}
    sc_service_area_name_dict = {service_area.get('name').strip(): service_area for service_area in sc_service_areas_data}
    log_info("Creating Service Catalogue dictionaries for quick lookup completed")
  except Exception as e:
    log_error("Dictionary lookup creation failed. Discontinuing processing products.py.")
    return None 

  sp_products_data = []
  parent = None
  team = None
  product_set = None
  service_area = None
  delivery_manager = None
  product_manager = None
  lead_developer = None
  for sp_product in sp_products['value']:
    log_info(f"Processing SharePoint product: {sp_product.get('fields', {}).get('ProductID', None)}")
    if sp_product.get('fields').get('DecommissionedProduct', '').upper() == 'YES':
      not_decommisioned = False
    else:
      not_decommisioned = True

    if not_decommisioned:
      product_id=sp_product.get('fields', {}).get('ProductID', None)
      if product_id:
        parent = None
        team = None
        product_set = None
        service_area = None
        subproductBool = False
        delivery_manager = None
        product_manager = None
        lead_developer = None
        if not re.match(r'^.+$', sp_product.get('fields', {}).get('Product')):
          log_error(f"Invalid name format for product_id: {product_id}")

        if not re.match(r'^[A-Z]{3,4}[0-9]{0,5}$', sp_product.get('fields', {}).get('ProductID')):
          log_error(f"Invalid productId format for product_id: {product_id}")

        if sp_product.get('fields', {}).get('ProductType') == "Subproduct":
          subproductBool = True
        else:
          subproductBool = False

        if parent_id := sp_product.get('fields', {}).get('ParentProductLookupId', None):
          try:
            parent = sp_product_dict.get(parent_id).get('fields').get('Product')
          except Exception as e:
            parent = None
            log_error(f"Parent product not found for product_id: {product_id}")

        if team_id := sp_product.get('fields', {}).get('TeamLookupId', None):
          try:
            team = sp_teams_dict.get(team_id).get('fields').get('Team')
          except Exception as e:
            team = None
            log_error(f"Team not found for product_id: {product_id}")

        if product_set_id := sp_product.get('fields', {}).get('ProductSetLookupId', None):
          try:
            product_set = sp_product_set_dict.get(product_set_id).get('fields').get('ProductSet')
          except Exception as e:
            product_set = None
            log_error(f"Product Set not found for product_id: {product_id}")

        if service_area_id := sp_product.get('fields', {}).get('ServiceAreaLookupId', None):
          try:
            service_area = sp_service_area_dict.get(service_area_id).get('fields').get('ServiceArea')
          except Exception as e:
            service_area = None
            log_error(f"Service Area not found for product_id: {product_id}")

        if delivery_manager_id := sp_product.get('fields', {}).get('DeliveryManagerLookupId', None):
          try:
            delivery_manager = sp_delivery_manager_dict.get(delivery_manager_id).get('fields').get('DeliveryManagerName')
          except Exception as e:
            delivery_manager = None
            log_error(f"Delivery Manager not found for product_id: {product_id}")

        if  product_manager_id := sp_product.get('fields', {}).get('ProductManagerLookupId', None):
          try:
            product_manager = sp_product_manager_dict.get(product_manager_id, {}).get('fields', {}).get('ProductManagerName')
          except Exception as e:
            product_manager = None
            log_error(f"Product Manager not found for product_id: {product_id}")

        if lead_developer_id := sp_product.get('fields', {}).get('LeadDeveloperLookupId', None):
          try:
            lead_developer = sp_lead_developer_dict.get(lead_developer_id, {}).get('fields', {}).get('Title', None)
          except Exception as e:
            lead_developer = None
            log_error(f"Lead Developer not found for product_id: {product_id}")

        sp_product_data = {
          "p_id": product_id,
          "name": clean_value(sp_product.get('fields', {}).get('Product', None)),
          "subproduct": subproductBool,
          "parent": parent,
          "description": clean_value(sp_product['fields'].get('Description_x0028_SourceData_x00', None)),
          "team": team,
          "phase": sp_product.get('fields', {}).get('field_7', None),
          "product_set": product_set,
          "service_area": service_area,
          "delivery_manager": delivery_manager,
          "product_manager": product_manager,
          "lead_developer": lead_developer,
          "slack_channel_id": sp_product.get('fields', {}).get('SlackchannelID', None),
          # "updated_by_id": 34
        }
        sp_products_data.append(sp_product_data)
  log_info(f"Found {len(sp_products_data)} Products in SharePoint after processing")

  sp_products_dict = {product.get('p_id'): product for product in sp_products_data}
  # Compare and update sp_product_data
  log_info("Processing prepared products sharepoint data for service catalogue ")
  change_count = 0 
  log_messages = []
  log_messages.append("************** Processing Products *********************")
  for sp_product in sp_products_data:
    p_id = sp_product.get('p_id')
    log_debug(f"Comparing Product p_id {p_id} :: {sp_product}")
    if p_id in sc_products_dict:
      try:
        sc_product = sc_products_dict.get(p_id)
        mismatch_flag = False
        for key in list(sp_product.keys()):
          compare_flag=False
          if key in sp_product and key in sc_product:
            compare_flag=True
          if compare_flag and key!='updated_by_id' and key!='subproduct' and key!="p_id":
            sp_value = clean_value(sp_product.get(key))
            if key == 'parent' or key == 'team' or key == 'product_set' or key == 'service_area':
              if sc_product.get(key):
                try:
                  sc_value = clean_value(sc_product.get(key).get('name'))
                except KeyError:
                  log_error(f"Key {key} not found in Service Catalogue data for p_id {p_id}")
                  sc_value = None
              else:
                sc_value = None
            else:
              try:
                sc_value=clean_value(sc_product.get(key))
              except KeyError:
                log_error(f"Key {key} not found in Service Catalogue data for p_id {p_id}")
                sc_value = None

            if sp_value is not None:
              if (sp_value or "").strip() != (sc_value or "").strip():
                log_messages.append(f"SC Updating Products p_id {p_id}({key}) :: {sc_value} -> {sp_value}")
                log_info(f"SC Updating Products p_id {p_id}({key}) :: {sc_value} -> {sp_value}")
                mismatch_flag = True
              else:
                del sp_product[key]
            
          elif compare_flag and key=='subproduct':
            if sp_product.get(key) != sc_product.get(key):
              log_messages.append(f"Updating Products p_id {p_id}({key}) :: {sp_value} -> {sc_value}")
              mismatch_flag = True
            else:
              del sp_product[key]

        if mismatch_flag:
          sp_product = fetchID(services, sp_product, sc_product_name_dict, "parent") if 'parent' in sp_product else sp_product
          sp_product = fetchID(services, sp_product, sc_team_name_dict, "team") if 'team' in sp_product else sp_product
          sp_product = fetchID(services, sp_product, sc_product_set_name_dict, "product_set") if 'product_set' in sp_product else sp_product
          sp_product = fetchID(services, sp_product, sc_service_area_name_dict, "service_area") if 'service_area' in sp_product else sp_product
          log_info(f"Updating Product :: p_id {p_id} :: {sc_product} -> {sp_product}")
          sc.update('products', sc_product.get('documentId'), sp_product)
          change_count += 1
      except Exception as e:
        log_error(f"Error processing product p_id {p_id}: {e}")
    else:
      try:
        sp_product = fetchID(services, sp_product, sc_product_name_dict, "parent")
        sp_product = fetchID(services, sp_product, sc_team_name_dict, "team")
        sp_product = fetchID(services, sp_product, sc_product_set_name_dict, "product_set")
        sp_product = fetchID(services, sp_product, sc_service_area_name_dict, "service_area")
        log_messages.append(f"Adding Product :: sp_product")
        log_info(f"Adding Product :: {sp_product}")
        sc.add('products', sp_product)
        change_count += 1
      except Exception as e:
        log_error(f"Error adding product p_id {p_id}: {e}")
        continue

  for sc_product in sc_products_data:
    try:
      p_id = sc_product.get('p_id').strip()
      if p_id not in sp_products_dict and 'HMPPS' not in p_id and 'DPS999' not in p_id:
        log_messages.append(f"Deleting product :: {sc_product.get('p_id')}")
        log_info(f"Deleting product  :: {sc_product.get('p_id')}")
        sc.delete('products', sc_product.get('documentId'))
        change_count += 1
    except Exception as e:
      log_error(f"Error deleting product {sc_product.get('p_id')}: {e}")
      continue

  log_messages.append(f"Products processed {change_count} in Service Catalogue") 
  log_info(f"Products processed {change_count} in Service Catalogue")
  log_messages.append("*******************************************************")
  return log_messages
    