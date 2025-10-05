

import httpx
import backoff
import random
import time
import os
import json
from openai import OpenAI
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



TRICK_LOCATIONS = [
    "indiana", # contains "india"
    "indianapolis"# ALSO CONTAINS INDIA! >:(
]

IDEAL_LOCATIONS = []
with open("ideal_locations.json") as f:
    IDEAL_LOCATIONS = list(map(lambda x:x.lower(), json.loads(f.read())))


def is_location_ok(location):
    location = location.lower()
    for tl in TRICK_LOCATIONS:
        if tl in location: return False # Bad location, skip

    for l in IDEAL_LOCATIONS:
        if l in location:
            return True
    return False





@backoff.on_exception(backoff.expo, httpx.RequestError, max_time=60)
def get_contributors(repo):
    owner = repo['owner']['login']
    name = repo['name']
    key = f"{owner}/{name}"
    if seen_repos.get(key):
        print("ALREADY SEEN REPO: (skipping)", key)
        return []

    contributors_response = httpx.get(
        f"https://api.github.com/repos/{owner}/{name}/contributors",
        headers=HEADERS,
        params={'per_page': 100}
    )
    contributors = contributors_response.json()

    seen_repos.set(key,True)
    seen_repos.save()

    return list(map(lambda cont: cont["login"], contributors))



@backoff.on_exception(backoff.expo, httpx.RequestError, max_time=60)
def find_repos():
    # ignore the top few most popular pages of godot repos; we dont want to spend ages searching.
    random_page = 3 + random.randint(3,100)
    response = httpx.get(
        'https://api.github.com/search/repositories',
        headers=HEADERS,
        params={
            'q': 'language:GDScript', 
            'per_page': 10,
            'page': random_page,
            'sort': 'stars'
        }
    )

    repos = response.json()['items']
    return repos




@backoff.on_exception(backoff.expo, httpx.RequestError, max_time=60)
def get_user_info(username):
    # if seen_users.get(username):
    #     return None

    response = httpx.get(f'https://api.github.com/users/{username}', headers=HEADERS)
    user = response.json()
    seen_users.set(username,True); seen_users.save()
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
        print(f"Gathering Contributors... {(100*i)/len(repos):.2f}% done")
        users = users + get_contributors(repo)
        # time.sleep(REQUESTS_PER_SECOND)
    
    for i,u in enumerate(users):
        print(f"Analyzing Users... {(100*i)/len(users):.2f}% done")
        info = get_user_info(u)
        # time.sleep(REQUESTS_PER_SECOND)

        if info and info.get("location") and is_location_ok(info["location"]):
            print("FOUND USER:", info["login"], info["location"])
            promising_users.set(info["login"], True)
            promising_users.save()



def update_country_count():
    cc = {}
    d={}
    with open("promising_users.json","r") as f:
        d = json.loads(f.read())
        for u,t in d.items():
            data = get_user_info(u)
            loc = data["location"].strip().lower()
            d[u] = loc
            cc[loc] = cc.get(loc,0)+1

    with open("promising_users.json","w") as f:
        f.write(json.dumps(d))

    with open("seen_country_count.json","w+") as f:
        f.write(json.dumps(cc,indent=4))



for i in range(5):
    main()


