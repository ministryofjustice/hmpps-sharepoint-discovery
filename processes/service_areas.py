import os
from time import sleep
from classes.slack import Slack
from classes.service_catalogue import ServiceCatalogue
from classes.sharepoint import SharePoint
from utilities.job_log_handling import log_debug, log_error, log_info, log_critical

class Services:
  def __init__(self, sc_params, slack_params):
    self.sc = ServiceCatalogue(sc_params)
    self.sp = SharePoint(sp_params)
    self.slack = Slack(slack_params)

def process_sc_service_areas(services, max_threads=10):
  sc = services.sc
  sp = services.sp
  log_info('Processing Service Areas ')
  try:
    sc_service_areas_data = sc.get_all_records(sc.service_areas_get)
    log_info(f'Found {len(sc_service_areas_data)} service areas in Service Catalogue before processing')
  except Exception as e:
    log_error(f'Error fetching service areas from Service Catalogue: {e}, discontinuing processing service_areas.py.')
    return None

  try:
    sp_service_areas = sp.get_sharepoint_lists(services, 'Service Areas')
    log_info(f'Found {len(sp_service_areas.get('value'))} Service Areas in SharePoint')
  except Exception as e:
    log_error(f'Error fetching SharePoint service areas: {e}, discontinuing processing service_areas.py.')
    return None

  try:
    log_info('Fetching service owners data from Sharepoint list')
    sp_service_owner_data = sp.get_sharepoint_lists(services, 'Service Owners')
    sp_service_onwers_dict = {service_owner.get('fields').get('ServiceOwnerLookupId'): service_owner for service_owner in sp_service_owner_data.get('value')}
    log_info(f'Fetching service owners data from Sharepoint list completed successfully.')
  except Exception as e:
    log_error(f'Error fetching SharePoint service owners: {e}')

  sp_service_areas_data = []
  log_info('Preparing SharePoint service areas data for processing')
  for sp_service_area in sp_service_areas.get('value'):
    try:
      service_area_id= sp_service_area.get('fields').get('ServiceAreaID', None)
      if service_area_id:
        service_owner_id = sp_service_area.get('fields').get('ServiceOwnerLookupId')
        if service_owner_id in sp_service_onwers_dict:
          sp_service_owner = sp_service_onwers_dict.get(service_owner_id)
          service_owner = sp_service_owner.get('fields').get('ServiceOwnerName')
        sp_service_area_data = {
            "sa_id": service_area_id,
            "name": sp_service_area.get('fields').get('ServiceArea'),
            "owner": service_owner,
            "updated_by_id": 34
          }
        sp_service_areas_data.append(sp_service_area_data)
    except Exception as e:
      log_error(f'Error preparing SharePoint service area data {sp_service_area}: {e}')
      return None 

  log_info('SharePoint service areas prepared successfully for SC processing.')

  try:
    log_info('Creating Service Catalogue service areas dictionary')
    sc_service_areas_dict = {service_area.get('attributes').get('sa_id'): service_area for service_area in sc_service_areas_data}
    sp_service_areas_dict = {service_area.get('sa_id'): service_area for service_area in sp_service_areas_data}
    log_info(f'Creating lookup dictionaries completed successfully.')
  except Exception as e:
    log_error(f'Error creating lookup dictionaries: {e}, discontinuing processing service_areas.py.')
    return None

  # Compare and update sp_service_area_data
  change_count = 0
  log_messages = []
  log_info("Processing prepared service area sharepoint data for service catalogue ")
  log_messages.append("************** Processing Service Areas *********************")
  for sp_service_area in sp_service_areas_data:
    sa_id = sp_service_area.get('sa_id')
    if sc_service_areas_dict.get(sa_id):
      log_info(f"Comparing Service Area {sa_id}")
      sc_service_area = sc_service_areas_dict.get(sa_id)
      mismatch_flag = False
      for key in sp_service_area.keys():
        compare_flag=False
        if sa_id in sc_service_areas_dict and key in sp_service_area and key in sc_service_area['attributes']:
          compare_flag=True
        if compare_flag and key!='updated_by_id':
          sp_value = sp_service_area.get(key)
          try:
            sc_value = sc_service_area.get('attributes').get(key)
          except KeyError:
            log_error(f"Key {key} not found in Service Catalogue data for sa_id {sa_id}")
          if sp_value is not None and sc_value is not None:
            if sp_value.strip() != sc_value.strip():
              log_messages.append(f"Updating Service Areas sa_id {sa_id}({key}) :: {sc_value} -> {sp_value}")
              log_info(f"Updating Service Areas sa_id {sa_id}({key}) :: {sc_value} -> {sp_value}")
              mismatch_flag = True
      if mismatch_flag:
        try:
          sc.update('service-areas', sc_service_area.get('id'), sp_service_area)
        except Exception as e:
          log_error(f"Error updating Service Area {sa_id}: {e}")
        change_count += 1
    else:
      log_messages.append(f"Adding Service Area :: {sp_service_area}")
      log_info(f"Adding Service Area :: {sp_service_area}")
      try:
        sc.add('service-areas', sp_service_area)
      except Exception as e:
        log_error(f"Error adding Service Area {sa_id}: {e}")
      change_count += 1

  for sc_service_area in sc_service_areas_data:
    sa_id = sc_service_area.get('attributes').get('sa_id')
    if sa_id not in sp_service_areas_dict and 'SP' not in sa_id:
      log_messages.append(f"Unpublishing Service Area :: {sc_service_area}")
      log_info(f"Unpublishing Service Area :: {sc_service_area}")
      try:
        sc.unpublish('service-areas', sc_service_area.get('id'))
      except Exception as e:
        log_error(f"Error unpublishing Service Area {sa_id}: {e}")
      change_count += 1

  log_messages.append(f"Service Areas processed {change_count} in Service Catalogue") 
  log_info(f"Service Areas processed {change_count} in Service Catalogue")
  return log_messages