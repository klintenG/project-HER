"""Operator tool to clear a stuck deployment maintenance lock in Firestore."""
import argparse
import subprocess
import requests
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', default='project-her-510715')
    args = parser.parse_args()

    token = subprocess.check_output(['gcloud', 'auth', 'print-access-token'], text=True).strip()
    url = f'https://firestore.googleapis.com/v1/projects/{args.project}/databases/(default)/documents/her_portfolio/policy'
    headers = {'Authorization': 'Bearer ' + token}

    current = None
    for attempt in range(3):
        try:
            response = requests.get(url, headers=headers, timeout=(10, 30))
            response.raise_for_status()
            current = response.json()
            break
        except (requests.Timeout, requests.ConnectionError):
            if attempt == 2: raise
            time.sleep(attempt + 1)
    fields = current.get('fields', {})
    is_maintenance = fields.get('maintenance', {}).get('booleanValue', False)
    owner = fields.get('maintenance_owner', {}).get('stringValue', '')

    print(f'Current maintenance state: {is_maintenance} (owner present: {bool(owner)})')
    if not is_maintenance:
        print("Maintenance is already False. No changes needed.")
        return

    params = [('updateMask.fieldPaths', 'maintenance'), ('updateMask.fieldPaths', 'maintenance_owner')]
    update_fields = {
        'maintenance': {'booleanValue': False},
        'maintenance_owner': {'stringValue': ''}
    }
    params.append(('currentDocument.updateTime', current['updateTime']))
    response = requests.patch(url, headers=headers, params=params, json={'fields': update_fields}, timeout=(10, 30))
    response.raise_for_status()

    check_response = requests.get(url, headers=headers, timeout=(10, 30))
    check_response.raise_for_status()
    check = check_response.json()
    assert check['fields']['maintenance']['booleanValue'] is False
    print("Deployment maintenance lock cleared successfully. The studio is reopened for admissions and deployments.")


if __name__ == '__main__':
    main()

