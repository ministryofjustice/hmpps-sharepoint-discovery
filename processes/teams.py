import logging
import os
import json
import requests
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

def process_sc_teams(services, max_threads=10):
  sc = services.sc
  sp = services.sp
  log = services.log

  sc_teams_data = sc.get_all_records(sc.teams_get)
  log.info(f'Service Catalogue teams before processing - {len(sc_teams_data)} ...')
  sp_teams = sp.get_sharepoint_lists('Teams')
  log.info(f'Found {len(sp_teams["value"])} teams in SharePoint...')
  sp_teams_data = []
  for sp_team in sp_teams["value"]:
      sp_team_data = {
        "t_id": sp_team['fields']['TeamID'],
        "name": sp_team['fields']['Team'],
        "description": "n/a",
        "slack_channel": "n/a",
        "updated_by_id": 33
      }
      sp_teams_data.append(sp_team_data)
  # Create a dictionary for quick lookup of sc_teams_data by t_id
  sc_teams_dict = {team['attributes']['t_id']: team for team in sc_teams_data}
  sp_teams_dict = {team['t_id']: team for team in sp_teams_data}
  # Compare and update sp_teams_data
  change_count = 0  
  log_messages = []
  log_messages.append("************** Processing Teams *********************")
  for sp_team in sp_teams_data:
    t_id = sp_team['t_id']
    if t_id in sc_teams_dict:
      sc_team = sc_teams_dict[t_id]
      if sp_team['name'].strip() != sc_team['attributes']['name'].strip():
        log_messages.append(f"Updating Team ::  t_id {t_id} :: {sc_team} -> {sp_team}")
        log.info(f"Updating Team name :: t_id {t_id} :: {sc_team} -> {sp_team}")  
        sc.update('teams', sc_team['id'], sp_team)
        change_count += 1
    else:
      log_messages.append(f"Adding team :: {sp_team['name']}")
      log.info(f"Adding team :: {sp_team['name']}")
      sc.add('teams', sp_team)
      change_count += 1

  for sc_team in sc_teams_data:
    t_id = sc_team['attributes']['t_id']
    if t_id not in sp_teams_dict:
      log_messages.append(f"Unpublishing team :: {sc_team}")
      log.info(f"Unpublishing team :: {sc_team}")
      sc.unpublish('teams', sc_team['id'])
      change_count += 1

  log_messages.append(f"Teams processed {change_count} in Service Catalogue") 
  log.info(f"Teams processed {change_count} in Service Catalogue")
  return log_messages
    