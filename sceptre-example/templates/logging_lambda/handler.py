# This is a demonstration lambda to show that it along with its dependencies can be
# packaged up and deployed.
import requests
import os


def lambda_handler(event, context):
    print(f'My special env: {os.getenv("SPECIAL_ENV")}')
    response = requests.get("https://api.ipify.org?format=json")
    if response.ok:
        print(f'My ip: {response.json()["ip"]}')
