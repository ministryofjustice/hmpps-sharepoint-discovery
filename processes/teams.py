from hmpps.services.job_log_handling import log_debug, log_error, log_info, log_warning
import json


def fetch_sp_teams_data(sp_teams):
  sp_teams_data = []
  log_debug('Preparing SharePoint teams data for service catalogue processing')
  for sp_team in sp_teams['value']:
    if team_id := sp_team.get('fields').get('TeamID', None):
      log_debug(f'Processing team {team_id} from SharePoint')
      sp_team_data = {
        't_id': team_id,
        'name': sp_team.get('fields').get('Team'),
        'budget_code': sp_team.get('fields').get('BudgetCode'),
        'confluence_link': sp_team.get('fields').get('ConfluenceLink'),
        # "description": "n/a",  field not available in SC
        # "slack_channel": "n/a", Not populated so commenting out
        # "updated_by_id": 34 Not working in strapi5
      }
      sp_teams_data.append(sp_team_data)
  log_debug(f'sp_teams_data is:\n{json.dumps(sp_teams_data, indent=2)}')
  log_info('SharePoint teams prepared successfully for SC processing.')
  return sp_teams_data


def process_sc_teams(services):
  def log_and_append(message):
    log_info(message)
    log_messages.append(message)

  sc = services.sc
  sp = services.sp
  change_count = 0
  log_messages = []

  # Service Catalogue
  log_info('Creating Lookup dictionaries ')
  sc_teams_data = sc.get_all_records('teams')

  if not sc_teams_data:
    log_warning('No teams returned from Service Catalogue')
  sc_teams_dict = {team.get('t_id'): team for team in sc_teams_data}

  if sp_teams_data := fetch_sp_teams_data(sp.data['Teams']):
    sp_teams_dict = {team.get('t_id'): team for team in sp_teams_data}
  else:
    log_error('No teams returned from Sharepoint')
    return None

  # Quick summary before we start
  log_info(f'Found {len(sp.data["Teams"].get("value", []))} teams in Sharepoint')
  log_info(f'Found {len(sc_teams_data)} teams in Service Catalogue')

  # Compare and update sp_teams_data
  log_info('Processing prepared teams sharepoint data for service catalogue ')
  log_info('************** Processing Teams *********************')

  for sp_team in sp_teams_data:
    t_id = sp_team.get('t_id')

    # If the record doesn't exist in service catalogue, add it and continue
    if not sc_teams_dict.get(t_id):
      log_and_append(f'Adding Team :: {sp_team}')
      sc.add('teams', sp_team)
      change_count += 1
      continue

    # Otherwise do the comparisons
    log_info(f'Comparing team {t_id} from SharePoint')
    sc_team = sc_teams_dict.get(t_id, {})
    # Add or update teams in Service Catalogue
    for key in sp_team.keys():
      if t_id in sc_teams_dict and key in sp_team and key in sc_team:
        sp_value = str(sp_team.get(key, '') or '').strip()
        sc_value = str(sc_team.get(key, '') or '').strip()
        if sp_value != sc_value:
          log_and_append(
            f'Updating Team t_id {t_id}({key}) :: {sc_value} -> {sp_value}'
          )
          sc.update('teams', sc_team.get('documentId'), sp_team)
          change_count += 1
        else:
          log_debug(f'No change for Team t_id {t_id} key ({key})')

  # Delete the teams that no longer exist in Sharepoint
  for sc_team in sc_teams_data:
    t_id = sc_team.get('t_id')
    if t_id not in sp_teams_dict:
      log_and_append(f'Deleting team :: {sc_team}')
      sc.delete('teams', sc_team.get('documentId'))
      change_count += 1

  log_and_append(f'Teams in Service Catalogue processed: {change_count}')
  return log_messages
