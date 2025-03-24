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

def process_sc_service_areas(services, max_threads=10):
  sc = services.sc
  sp = services.sp
  log = services.log

  sc_service_area_data = sc.get_all_records(sc.service_areas_get)
  log.info(f'Found {len(sc_service_area_data)} service areas in Service Catalogue before processing')
  sp_service_areas = sp.get_sharepoint_lists('Service Areas','ServiceAreaID,ServiceArea')
  sp_service_owner_data = sp.get_sharepoint_lists('Service Owners','ServiceOwnerLookupId')
  # print(sp_service_owner_data)
  sp_service_onwers_dict = {service_owner['fields']['ServiceOwnerLookupId']: service_owner for service_owner in sp_service_owner_data['value']}
  log.info(f'Found {len(sp_service_areas["value"])} Service Areas in SharePoint...')
  sp_service_areas_data = []
  for sp_service_area in sp_service_areas["value"]:
    service_owner_id = sp_service_area['fields']['ServiceOwnerLookupId']
    if service_owner_id in sp_service_onwers_dict:
      sp_service_owner = sp_service_onwers_dict[service_owner_id]
      service_owner = sp_service_owner['fields']['ServiceOwnerName']
    sp_service_area_data = {
        "sa_id": sp_service_area['fields']['ServiceAreaID'],
        "name": sp_service_area['fields']['ServiceArea'],
        "owner": service_owner,
        "updated_by_id": None
      }
    sp_service_areas_data.append(sp_service_area_data)
  # Create a dictionary for quick lookup of sc_service_area_data by t_id
  sc_service_areas_dict = {product_set['attributes']['sa_id']: product_set for product_set in sc_service_area_data}
  # Compare and update sp_service_area_data
  for sp_service_area in sp_service_areas_data:
    sa_id = sp_service_area['sa_id']
    if sa_id in sc_service_areas_dict:
      sc_service_area = sc_service_areas_dict[sa_id]
      if sp_service_area['name'].strip() != sc_service_area['attributes']['name'].strip() or sp_service_area['owner'].strip() != sc_service_area['attributes']['owner'].strip():
        log.info(f"SC Updating Service Areas for sa_id {sa_id} from {sc_service_area} to {sp_service_area}")
        log.info("--------------------")
        # sc.update('service-areas', sc_service_area['id'], {sp_service_area})
    else:
      log.info(f"Adding Service Area {sp_service_area['name']} to Service Catalogue")
      log.info("--------------------")
      # sc.add('service-areas', sp_service_area)
    