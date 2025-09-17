import os
import json
import requests
import re
from time import sleep
from classes.slack import Slack
from classes.service_catalogue import ServiceCatalogue
from classes.sharepoint import SharePoint
from slugify import slugify
from utilities.job_log_handling import log_debug, log_error, log_info, log_critical

class Services:
  def __init__(self, sc_params, slack_params):
    self.sc = ServiceCatalogue(sc_params)
    self.sp = SharePoint(sp_params)
    self.slack = Slack(slack_params)

def process_sc_teams(services, max_threads=10):
  sc = services.sc
  sp = services.sp
  log_info('Processing Teams ')
  try:
    sc_teams_data = sc.get_all_records(sc.teams_get)
  except Exception as e:
    log_error(f'Error fetching teams from Service Catalogue: {e}, discontinuing processing teams.py.')
    return None

  try:
    sp_teams = sp.get_sharepoint_lists(services, 'Teams')
  except Exception as e:
    log_error(f'Error fetching SharePoint teams: {e}, discontinuing processing teams.py.')
    return None

  log_info(f'Found {len(sp_teams.get('value'))} teams in SharePoint')
  sp_teams_data = []
  log_info(f'Preparing SharePoint teams data for service catalogue processing')
  for sp_team in sp_teams['value']:
    if team_id := sp_team.get('fields').get('TeamID', None):
      log_debug(f"Processing team {team_id} from SharePoint")
      team_name = sp_team.get('fields').get('Team', None)
      sp_team_data = {
        "t_id": team_id,
        "name": team_name,
        "slug": slugify(team_name) if team_name else None,
        # "description": "n/a",  field not available in SC 
        # "slack_channel": "n/a", Not populated so commenting out
        # "updated_by_id": 34 Not working in strapi5 
      }
      sp_teams_data.append(sp_team_data)
  log_info('SharePoint teams prepared successfully for SC processing.')

  try:
    log_info('Creating Lookup dictionaries ')
    sc_teams_dict = {team.get('t_id'): team for team in sc_teams_data}
    sp_teams_dict = {team.get('t_id'): team for team in sp_teams_data}
    log_info('Lookup dictionaries created successfully.')
  except Exception as e:
    log_error(f'Error creating lookup dictionaries: {e}, discontinuing processing teams.py.')
    return None

  # Compare and update sp_teams_data
  change_count = 0  
  log_messages = []
  log_info("Processing prepared teams sharepoint data for service catalogue ")
  log_messages.append("************** Processing Teams *********************")
  for sp_team in sp_teams_data:
    t_id = sp_team.get('t_id')
    log_info(f"Comparing team {t_id} from SharePoint")
    try:
      if t_id in sc_teams_dict:
        sc_team = sc_teams_dict.get(t_id)
        if sp_team['name'].strip() != sc_team.get('name').strip() or sp_team['slug'] != sc_team.get('slug'):
          log_messages.append(f"Updating Team ::  t_id {t_id} :: {sc_team} -> {sp_team}")
          log_info(f"Updating Team name :: t_id {t_id} :: {sc_team} -> {sp_team}")
          try:
            sc.update('teams', sc_team.get('documentId'), sp_team)
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
    t_id = sc_team.get('t_id')
    try:
      if t_id not in sp_teams_dict:
        log_messages.append(f"Unpublishing team :: {sc_team}")
        log_info(f"Unpublishing team :: {sc_team}")
        try:
          sc.unpublish('teams', sc_team.get('documentId'))
        except Exception as e:
          log_error(f"Error unpublishing Team {t_id}: {e}")
        change_count += 1
    except Exception as e:
      log_error(f"Error unpublishing team {t_id}: {e}")

  log_messages.append(f"Teams processed {change_count} in Service Catalogue") 
  log_info(f"Teams processed {change_count} in Service Catalogue")
  return log_messages
    