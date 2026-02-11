import requests
import json
import os
from azure.identity import ClientSecretCredential
from hmpps.services.job_log_handling import (
  log_debug,
  log_info,
  log_error,
  log_critical,
)


class SharePoint:
  def __init__(
    self, az_tenant_id='', sp_client_id='', sp_client_secret='', sp_site_id=''
  ):
    # default variables
    # page_size = 10
    # pagination_page_size = f'&pagination[pageSize]={page_size}'

    self.az_tenant_id = az_tenant_id or os.getenv('AZ_TENANT_ID', '')
    self.sp_client_id = sp_client_id or os.getenv('SP_CLIENT_ID', '')
    self.sp_client_secret = sp_client_secret or os.getenv('SP_CLIENT_SECRET', '')
    self.sp_site_id = sp_site_id or os.getenv('SP_SITE_ID', '')

    try:
      credential = ClientSecretCredential(
        self.az_tenant_id, self.sp_client_id, self.sp_client_secret
      )
      self.token = credential.get_token('https://graph.microsoft.com/.default').token
    except Exception as e:
      log_critical(f'Unable to get token - {e}')

    self.api_headers = {
      'Authorization': f'Bearer {self.token}',
      'Accept': 'application/json',
    }
    self.url = f'https://graph.microsoft.com/v1.0/sites/{self.sp_site_id}/lists'
    self.connection_ok = self.test_connection()
    self.data = {}
    self.dict = {}
    self.populate_sp_data()

  """
  Test connection to the Service Catalogue
  """

  def test_connection(self):
    # Test connection to Sharepoint
    try:
      log_info(f'Testing connection to Sharepoint - {self.url}')
      r = requests.get(self.url, headers=self.api_headers)
      log_info(f'Successfully connected to Sharepoint - {self.url}. {r.status_code}')
      self.lists_data = r.json()
      return True
    except Exception as e:
      log_critical(f'Unable to connect to Sharepoint - {e}')
      return False

  """
  Main call to sharepoint to return lists
  """

  def get_sharepoint_lists(self, list_name):
    if not self.lists_data:
      log_critical(
        'No sharepoint lists data available. Please run test_connection first.'
      )
      raise Exception('No Sharepoint list data available - cannot continue')
    log_info(f'Fetching SharePoint {list_name} data')
    try:
      list_item = next(
        (
          sp_list
          for sp_list in self.lists_data['value']
          if sp_list['displayName'] == list_name
        ),
        None,
      )
      if list_item:
        list_id = list_item['id']
        # Make a request to get fields metadata from the specified list
        fields_url = (
          f'https://graph.microsoft.com/v1.0/sites/{self.sp_site_id}/lists/'
          f'{list_id}/columns'
        )
        fields_response = requests.get(fields_url, headers=self.api_headers)
        if fields_response.status_code == 200:
          # Make a request to get items from the specified list with all fields
          items_url = (
            f'https://graph.microsoft.com/v1.0/sites/{self.sp_site_id}/lists/'
            f'{list_id}/items?expand=fields'
          )
          items_response = requests.get(items_url, headers=self.api_headers)
          if items_response.status_code == 200:
            items = items_response.json()
            log_info(f'found {len(items)} items in Sharepoint {list_name}')
            return items
          else:
            log_error(
              f'Failed to retrieve items from {list_name} list: '
              f'{items_response.status_code} {items_response.text}'
            )
        else:
          log_error(
            f'Failed to retrieve fields metadata from {list_name} list: '
            f'{fields_response.status_code} {fields_response.text}'
          )
      else:
        log_error(f'List {list_name} not found.')
    except Exception as e:
      log_critical(f'Unable to retrieve data from Sharepoint - {e}')

    return None

  # Make a dictionary with the ID as the key field
  def make_dict(self, data):
    log_debug(f'data: {json.dumps(data, indent=2)}')
    dictionary = {item.get('id'): item for item in data.get('value')}
    return dictionary

  def populate_sp_data(self):
    sp_lists = [
      'Service Areas',
      'Product Set',
      'Teams',
      'Service Owners',
      'Product Managers',
      'Delivery Managers',
      'Lead Developers',
      'Products and Teams Main List',
      'Technical Architects',
    ]
    for sp_list in sp_lists:
      if loaded_list := self.get_sharepoint_lists(sp_list):
        log_info(
          f'Found {len(loaded_list.get("value", []))} {sp_list} items in SharePoint'
        )
        self.data[sp_list] = loaded_list
        self.dict[sp_list] = self.make_dict(self.data[sp_list])
      else:
        log_error(f'No {sp_list} items found in Sharepoint')
        self.data[sp_list] = []
        self.dict[sp_list] = {}
