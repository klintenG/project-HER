"""Operator tool to clear a stuck deployment maintenance lock in Firestore."""
import argparse
import subprocess
import requests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', default='project-her-510715')
    args = parser.parse_args()

    token = subprocess.check_output(['gcloud', 'auth', 'print-access-token'], text=True).strip()
    url = f'https://firestore.googleapis.com/v1/projects/{args.project}/databases/(default)/documents/her_portfolio/policy'
    headers = {'Authorization': 'Bearer ' + token}

    current = requests.get(url, headers=headers, timeout=30).json()
    fields = current.get('fields', {})
    is_maintenance = fields.get('maintenance', {}).get('booleanValue', False)
    owner = fields.get('maintenance_owner', {}).get('stringValue', '')

    print(f"Current maintenance state: {is_maintenance} (owner: '{owner}')")
    if not is_maintenance:
        print("Maintenance is already False. No changes needed.")
        return

    params = [('updateMask.fieldPaths', 'maintenance'), ('updateMask.fieldPaths', 'maintenance_owner')]
    update_fields = {
        'maintenance': {'booleanValue': False},
        'maintenance_owner': {'stringValue': ''}
    }
    response = requests.patch(url, headers=headers, params=params, json={'fields': update_fields}, timeout=30)
    response.raise_for_status()

    check = requests.get(url, headers=headers, timeout=30).json()
    assert check['fields']['maintenance']['booleanValue'] is False
    print("Deployment maintenance lock cleared successfully. The studio is reopened for admissions and deployments.")


if __name__ == '__main__':
    main()

