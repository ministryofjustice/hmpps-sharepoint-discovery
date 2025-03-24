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
  sp_teams = sp.get_sharepoint_lists('Teams','TeamID,Team')
  log.info(f'Found {len(sp_teams["value"])} teams in SharePoint...')
  sp_teams_data = []
  for sp_team in sp_teams["value"]:
      sp_team_data = {
        "t_id": sp_team['fields']['TeamID'],
        "name": sp_team['fields']['Team'],
        "description": "n/a",
        "slack_channel": "n/a",
        "updated_by_id": None
      }
      sp_teams_data.append(sp_team_data)
  # Create a dictionary for quick lookup of sc_teams_data by t_id
  sc_teams_dict = {team['attributes']['t_id']: team for team in sc_teams_data}
    
  # Compare and update sp_teams_data
  for sp_team in sp_teams_data:
    t_id = sp_team['t_id']
    if t_id in sc_teams_dict:
      sc_team = sc_teams_dict[t_id]
      if sp_team['name'].strip() != sc_team['attributes']['name'].strip():
        log.info(f"SC Updating team name for t_id {t_id} from {sc_team['attributes']['name']} to {sp_team['name']}")
        sc.update('teams', sc_team['id'], {"name": sp_team['name']})
    else:
      log.info(f"Adding team {sp_team['name']} to Service Catalogue")
      sc.add('teams', sp_team)
    