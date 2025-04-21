import os
from time import sleep
from classes.slack import Slack
from classes.service_catalogue import ServiceCatalogue
from classes.sharepoint import SharePoint
import globals

log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()

class Services:
  def __init__(self, sc_params, slack_params, log):
    self.sc = ServiceCatalogue(sc_params, log)
    self.sp = SharePoint(sp_params, log)
    self.slack = Slack(slack_params, log)
    self.log = log

def process_sc_service_areas(max_threads=10):
  sc = globals.services.sc
  sp = globals.services.sp
  log = globals.services.log

  sc_service_areas_data = sc.get_all_records(sc.service_areas_get)
  if not sc_service_areas_data:
    globals.error_messages.append(f'Errors occurred while fetching service areas from Service Catalogue')
  else:
    log.info(f'Found {len(sc_service_areas_data)} service areas in Service Catalogue before processing')
  sp_service_areas = sp.get_sharepoint_lists('Service Areas')
  sp_service_owner_data = sp.get_sharepoint_lists('Service Owners')
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
        "updated_by_id": 33
      }
    sp_service_areas_data.append(sp_service_area_data)
  # Create a dictionary for quick lookup of sc_service_area_data by t_id
  sc_service_areas_dict = {service_area['attributes']['sa_id']: service_area for service_area in sc_service_areas_data}
  sp_service_areas_dict = {service_area['sa_id']: service_area for service_area in sp_service_areas_data}

  # Compare and update sp_service_area_data
  change_count = 0
  log_messages = []
  log_messages.append("************** Processing Service Areas *********************")
  for sp_service_area in sp_service_areas_data:
    sa_id = sp_service_area['sa_id']
    sc_service_area = sc_service_areas_dict[sa_id]
    mismatch_flag = False
    for key in sp_service_area.keys():
      compare_flag=False
      if sa_id in sc_service_areas_dict and key in sp_service_area and key in sc_service_area['attributes']:
        compare_flag=True
      if compare_flag and key!='updated_by_id':
        sp_value = sp_service_area[key]
        sc_value = sc_service_area['attributes'][key]
        if sp_value is not None and sc_value is not None:
          if sp_value.strip() != sc_value.strip():
            log_messages.append(f"Updating Service Areas sa_id {sa_id}({key}) :: {sc_value} -> {sp_value}")
            log.info(f"Updating Service Areas sa_id {sa_id}({key}) :: {sc_value} -> {sp_value}")
            mismatch_flag = True
    if mismatch_flag:
      sc.update('service-areas', sc_service_area['id'], sp_service_area)
      change_count += 1
    if sa_id not in sc_service_areas_dict:
      log_messages.append(f"Adding Service Area :: {sp_service_area}")
      log.info(f"Adding Service Area :: {sp_service_area}")
      sc.add('service-areas', sp_service_area)
      change_count += 1

  for sc_service_area in sc_service_areas_data:
    sa_id = sc_service_area['attributes']['sa_id']
    if sa_id not in sp_service_areas_dict and 'SP' not in sa_id:
      log_messages.append(f"Unpublishing Service Area :: {sc_service_area}")
      log.info(f"Unpublishing Service Area :: {sc_service_area}")
      sc.unpublish('service-areas', sc_service_area['id'])
      change_count += 1

  log_messages.append(f"Service Areas processed {change_count} in Service Catalogue") 
  log.info(f"Service Areas processed {change_count} in Service Catalogue")
  return log_messages