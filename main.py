

import httpx
import backoff
import time
import os
import json
from dotenv import load_dotenv
from pickledb import PickleDB


load_dotenv()

TOKEN = os.getenv('GITHUB_API_TOKEN')
HEADERS = {'Authorization': f'token {TOKEN}'} if TOKEN else {}

REQUESTS_PER_SECOND = 5000/3600 # 5000 reqs/hour. 




# keep track of which users/repos we have already seen.
seen_repos = PickleDB('seen_repos.json')
seen_users = PickleDB('seen_users.json')


# Keep track of what users have passed the location-test
promising_users = PickleDB('promising_users.json')




IDEAL_LOCATIONS = []
with open("ideal_locations.json") as f:
    IDEAL_LOCATIONS = list(map(lambda x:x.lower(), json.loads(f.read())))


def is_location_ok(location):
    location = location.lower()
    for l in IDEAL_LOCATIONS:
        if l in location:
            return True
    return False





@backoff.on_exception(backoff.expo, httpx.RequestError, max_time=60)
def get_contributors(repo):
    owner = repo['owner']['login']
    name = repo['name']

    contributors_response = httpx.get(
        f"https://api.github.com/repos/{owner}/{name}/contributors",
        headers=HEADERS,
        params={'per_page': 100}
    )
    contributors = contributors_response.json()
    
    return list(map(lambda cont: cont["login"], contributors))



@backoff.on_exception(backoff.expo, httpx.RequestError, max_time=60)
def find_repos():
    response = httpx.get(
        'https://api.github.com/search/repositories',
        headers=HEADERS,
        params={'q': 'language:GDScript', 'per_page': 8}
    )

    repos = response.json()['items']
    return repos




@backoff.on_exception(backoff.expo, httpx.RequestError, max_time=60)
def get_user_info(username):
    response = httpx.get(f'https://api.github.com/users/{username}', headers=HEADERS)
    user = response.json()
    # {
    #     'login': user['login'],
    #     'location': user.get('location'),
    #     'public_repos': user['public_repos']
    # }
    return user





def main():
    repos = find_repos()
    users = []
    for i,repo in enumerate(repos):
        print(f"Repos: {(100*i)/len(repos):.2f}% done")
        if seen_repos.get(repo):
            continue

        seen_repos.set(repo,True); seen_repos.save()
        users = users + get_contributors(repo)
        time.sleep(REQUESTS_PER_SECOND)
    
    for i,u in enumerate(users):
        print(f"Users: {(100*i)/len(users):.2f}% done")
        if seen_users.get(u):
            continue
        seen_users.set(u,True); seen_users.save()
        info = get_user_info(u)
        time.sleep(REQUESTS_PER_SECOND)

        print(info)
        if is_location_ok(info["location"]):
            promising_users.set(info["login"], True)


main()

