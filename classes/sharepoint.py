import requests
import logging
import json
from azure.identity import ClientSecretCredential
import globals
import utils.update_sc_scheduled_jobs as update_sc_scheduled_job

class SharePoint:
  def __init__(self, params, log_level=logging.INFO):
    logging.basicConfig(
      format='[%(asctime)s] %(levelname)s %(threadName)s %(message)s', level=log_level
    )
    # default variables
    # page_size = 10
    # pagination_page_size = f'&pagination[pageSize]={page_size}'

    self.log = logging.getLogger(__name__)
    self.az_tenant_id = params['az_tenant_id']
    self.sp_client_id = params['sp_client_id']
    self.sp_client_secret = params['sp_client_secret']
    self.sp_site_id = params['sp_site_id']
    try:
      credential = ClientSecretCredential(self.az_tenant_id, self.sp_client_id, self.sp_client_secret)
      self.token = credential.get_token('https://graph.microsoft.com/.default').token
    except Exception as e:
      self.log.critical(f'Unable to get token - {e}')
        
    self.api_headers = {
        'Authorization': f'Bearer {self.token}',
        'Accept': 'application/json'
        }
    self.url = f'https://graph.microsoft.com/v1.0/sites/{self.sp_site_id}/lists'
    self.connection_ok = self.test_connection()

  """
  Test connection to the Service Catalogue
  """

  def test_connection(self):
    # Test connection to Sharepoint
    try:
      self.log.info(f'Testing connection to Sharepoint - {self.url}')
      r = requests.get(self.url, headers=self.api_headers)
      self.log.info(
        f'Successfully connected to Sharepoint - {self.url}. {r.status_code}'
      )
      self.lists_data = r.json()
      return True
    except Exception as e:
      self.log.critical(f'Unable to connect to Sharepoint - {e}')
      return False
    
  def get_sharepoint_lists(self, list_name):
    if not self.lists_data:
      globals.error_messages.append(f"No Sharepoint lists data available. Please run test_connection first.")
      self.log.error("No lists data available. Please run test_connection first.")
      update_sc_scheduled_job.process_sc_scheduled_jobs('Failed')
      raise SystemExit()

    try:
      list_item = next((sp_list for sp_list in self.lists_data['value'] if sp_list['displayName'] == list_name), None)
      if list_item:
        list_id = list_item['id']
        # Make a request to get fields metadata from the specified list
        fields_url = f'https://graph.microsoft.com/v1.0/sites/{self.sp_site_id}/lists/{list_id}/columns'
        fields_response = requests.get(fields_url, headers=self.api_headers)
        if fields_response.status_code == 200:
          fields_data = fields_response.json()
          # Filter out invalid field names
          valid_field_names = [field['name'] for field in fields_data['value'] if 'name' in field]
          select_fields = ','.join(valid_field_names)
          # Make a request to get items from the specified list with all fields
          items_url = f'https://graph.microsoft.com/v1.0/sites/{self.sp_site_id}/lists/{list_id}/items?expand=fields'
          items_response = requests.get(items_url, headers=self.api_headers)
          if items_response.status_code == 200:
            items = items_response.json()
            return items
          else:
            self.log.error(f"Failed to retrieve items from {list_name} list: {items_response.status_code} {items_response.text}")
            globals.error_messages.append(f"Failed to retrieve items from {list_name} list: {items_response.status_code} {items_response.text}")
        else:
          self.log.error(f"Failed to retrieve fields metadata from {list_name} list: {fields_response.status_code} {fields_response.text}")
          globals.error_messages.append(f"Failed to retrieve items from {list_name} list: {items_response.status_code} {items_response.text}")
      else:
        self.log.error(f"List {list_name} not found.")
        globals.error_messages.append(f"List {list_name} not found.")
    except Exception as e:
      self.log.critical(f'Unable to connect to Sharepoint - {e}')
      return False