from hmpps.services.job_log_handling import log_error, log_info, log_debug
import json


def fetch_sp_service_areas_data(sp):
  sp_service_areas_data = []
  log_debug('Creating service owners dictionary')
  sp_service_owners_dict = {
    service_owner.get('fields').get('ServiceOwnerLookupId'): service_owner
    for service_owner in sp.data['Service Owners'].get('value')
  }

  log_info('Preparing SharePoint service areas data for processing')
  # this populates linked Service Onwers as well as the 'name' field
  for sp_service_area in sp.data['Service Areas'].get('value'):
    service_area = sp_service_area.get('fields').get('ServiceArea')
    if service_area_id := sp_service_area.get('fields').get('ServiceAreaID', None):
      log_debug(f'Service area ID for {service_area}: {service_area_id}')
      service_owner_id = sp_service_area.get('fields').get('ServiceOwnerLookupId', '')
      log_debug(f'Service owner ID: {service_owner_id}')
      sp_service_owner = sp_service_owners_dict.get(service_owner_id, {})
      # Could be be missing a service owner, so skip if it is..
      service_owner = sp_service_owner.get('fields', {}).get('ServiceOwnerName', '')
      sp_service_area_data = {
        'sa_id': service_area_id,
        'name': sp_service_area.get('fields').get('ServiceArea'),
        'owner': service_owner,
        # "updated_by_id": 34 Not working in strapi5
      }
      sp_service_areas_data.append(sp_service_area_data)

  log_info('SharePoint service areas prepared successfully for SC processing.')
  log_debug(f'sp_service_areas_data is:\n{json.dumps(sp_service_areas_data, indent=2)}')
  return sp_service_areas_data


def process_sc_service_areas(services):
  def log_and_append(message):
    log_info(message)
    log_messages.append(message)

  sc = services.sc
  sp = services.sp

  log_info('Processing Service Areas ')
  sc_service_areas_data = sc.get_all_records('service-areas')
  if not sc_service_areas_data:
    log_error('No service areas returned from the Service Catalogue')
    return None

  # Process Sharepoint Service Areas
  sp_service_areas_data = fetch_sp_service_areas_data(sp)

  log_info('Creating Service Catalogue service areas dictionary')
  sc_service_areas_dict = {
    service_area.get('sa_id'): service_area for service_area in sc_service_areas_data
  }
  sp_service_areas_dict = {
    service_area.get('sa_id'): service_area for service_area in sp_service_areas_data
  }
  log_debug('Lookup dictionaries created successfully.')

  # Quick summary before we start
  log_info(
    f'Found {len(sp.data["Service Areas"].get("value", []))} service areas in Sharepoint'
  )
  log_info(f'Found {len(sc_service_areas_data)} service areas in Service Catalogue')

  # Compare and update sp_service_area_data
  change_count = 0
  log_messages = []
  log_info('Processing prepared service area sharepoint data for service catalogue ')
  log_info('************** Processing Service Areas *********************')
  for sp_service_area in sp_service_areas_data:
    sa_id = sp_service_area.get('sa_id')

    # If the record doesn't exist in service catalogue, add it and continue
    if not sc_service_areas_dict.get(sa_id):
      log_and_append(f'Adding Service Area :: {sp_service_area}')
      sc.add('service-areas', sp_service_area)
      change_count += 1
      continue

    # Otherwise do the comparisons
    log_debug(f'Comparing Service Area {sa_id}')
    sc_service_area = sc_service_areas_dict.get(sa_id, {})
    log_debug(f'\ncomparing SC service area {sc_service_area} \nwith SP service area {sp_service_area}')
    for key in sp_service_area.keys():
      if (
        sa_id in sc_service_areas_dict
        and key in sp_service_area
        and key in sc_service_area
        and key != 'updated_by_id'
      ):
        sp_value = str(sp_service_area.get(key, '') or '').strip()
        sc_value = str(sc_service_area.get(key, '') or '').strip()
        if sp_value != sc_value:
          log_and_append(
            f'Updating Service Areas sa_id {sa_id}({key}) :: {sc_value} -> {sp_value}'
          )
          sc.update('service-areas', sc_service_area.get('documentId'), sp_service_area)
          change_count += 1
        else:
          log_info(f'No change for Service Area sa_id {sa_id} ({key})')

  # Delete those that no longer exist in Sharepoint
  for sc_service_area in sc_service_areas_data:
    sa_id = sc_service_area.get('sa_id')
    if sa_id not in sp_service_areas_dict and 'SP' not in sa_id:
      log_and_append(f'Deleting Service Area :: {sc_service_area}')
      sc.delete('service-areas', sc_service_area.get('documentId'))
      change_count += 1

  log_and_append(f'Service Areas in Service Catalogue processed: {change_count}')
  return log_messages
