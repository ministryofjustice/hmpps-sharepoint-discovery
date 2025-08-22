import os
import json
import requests
import re
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

def process_sc_teams(services, max_threads=10):
  sc = services.sc
  sp = services.sp

  sc_teams_data = sc.get_all_records(sc.teams_get)
  if not sc_teams_data:
    log_error(f'Errors occurred while fetching teams from Service Catalogue')
  else:
    log_info(f'Service Catalogue teams before processing - {len(sc_teams_data)} ...')
  try:
    sp_teams = sp.get_sharepoint_lists(services, 'Teams')
  except Exception as e:
    log_error(f'Error fetching SharePoint teams: {e}')

  log_info(f'Found {len(sp_teams.get('value'))} teams in SharePoint...')
  sp_teams_data = []
  log_info(f'Preparing SharePoint teams...')
  for sp_team in sp_teams['value']:
    if team_id := sp_team.get('fields').get('TeamID', None):
      log_debug(f"Processing team {team_id} from SharePoint")
      sp_team_data = {
        "t_id": team_id,
        "name": sp_team.get('fields').get('Team'),
        "description": "n/a",
        "slack_channel": "n/a",
        "updated_by_id": 34
      }
      sp_teams_data.append(sp_team_data)
  log_info('SharePoint teams prepared successfully for SC processing.')

  # Create a dictionary for quick lookup of sc_teams_data by t_id
  log_info('Creating Lookup dictionaries ...')
  try:
    sc_teams_dict = {team.get('attributes').get('t_id'): team for team in sc_teams_data}
  except Exception as e:
    log_error(f'Error creating SC teams dictionary: {e}')
    sc_teams_dict = {}

  try:
    sp_teams_dict = {team.get('t_id'): team for team in sp_teams_data}
  except Exception as e:
    log_error(f'Error creating SharePoint teams dictionary: {e}')
    sp_teams_dict = {}
  log_info('Lookup dictionaries created successfully.')

  # Compare and update sp_teams_data
  change_count = 0  
  log_messages = []
  log_info("Processing prepared teams sharepoint data for service catalogue ...")
  log_messages.append("************** Processing Teams *********************")
  for sp_team in sp_teams_data:
    t_id = sp_team.get('t_id')
    log_info(f"Processing team {t_id} from SharePoint")
    try:
      if t_id in sc_teams_dict:
        sc_team = sc_teams_dict.get(t_id)
        if sp_team.get('name').strip() != sc_team.get('attributes').get('name').strip():
          log_messages.append(f"Updating Team ::  t_id {t_id} :: {sc_team} -> {sp_team}")
          log_info(f"Updating Team name :: t_id {t_id} :: {sc_team} -> {sp_team}")
          try:
            sc.update('teams', sc_team.get('id'), sp_team)
          except Exception as e:
            log_error(f"Error updating Team {t_id}: {e}")
          change_count += 1
      else:
        log_messages.append(f"Adding team :: {sp_team.get('name')}")
        log_info(f"Adding team :: {sp_team.get('name')}")
        try:
          sc.add('teams', sp_team)
        except Exception as e:
          log_error(f"Error adding Team {t_id}: {e}")
        change_count += 1
    except Exception as e:
      log_messages.append(f"Error processing team {t_id}: {e}")

  for sc_team in sc_teams_data:
    t_id = sc_team.get('attributes').get('t_id')
    try:
      if t_id not in sp_teams_dict:
        log_messages.append(f"Unpublishing team :: {sc_team}")
        log_info(f"Unpublishing team :: {sc_team}")
        try:
          sc.unpublish('teams', sc_team.get('id'))
        except Exception as e:
          log_error(f"Error unpublishing Team {t_id}: {e}")
        change_count += 1
    except Exception as e:
      log_error(f"Error unpublishing team {t_id}: {e}")

  log_messages.append(f"Teams processed {change_count} in Service Catalogue") 
  log_info(f"Teams processed {change_count} in Service Catalogue")
  return log_messages
    