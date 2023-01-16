import requests
import json
import yaml
import os
from bs4 import BeautifulSoup
import re


nasa_key = os.environ['NASA_API_KEY']
covid_key = os.environ['COVID_API_KEY']
with open('config/states.json', 'r') as f:
  states = json.loads(f.read())

amc10_answers_path = 'config/amc10_answers.yml'
with open(amc10_answers_path, 'r') as f:
  amc10_answers = yaml.safe_load(f)


def get_question(category=None):
  url = 'https://scibowldb.com/api/questions/random'
  if category is not None:
    post_json = {
      'categories': [category]
    }
    resp = requests.post(url, json=post_json)
  else:
    resp = requests.get(url)
    
  body = json.loads(resp.content.decode('utf-8'))
  return body['question']['tossup_question'], body['question']['tossup_answer'], body['question']['tossup_format']


def get_apod():
  url = f"https://api.nasa.gov/planetary/apod?api_key={nasa_key}"
  return json.loads(requests.get(url).content.decode('utf-8'))


def get_earth_image(latitude=29.78, longitude=-95.33):
  url = f'https://api.nasa.gov/planetary/earth/assets?lon={longitude}&lat={latitude}&date=2018-01-01&&dim=0.10&api_key={nasa_key}'
  return json.loads(requests.get(url).content.decode('utf-8'))


def get_mars_image(date='2020-6-3'):
  url = f'https://api.nasa.gov/mars-photos/api/v1/rovers/curiosity/photos?earth_date={date}&api_key={nasa_key}'
  try:
    return json.loads(requests.get(url).content.decode('utf-8'))['photos']
  except:
    return None


def get_covid_stats(state):
  if len(state) == 2:
    state = state.upper()
  elif len(state.split()) == 1:
    state = states.get(state[0].upper() + state[1:])
  else:
    state = states.get(' '.join(map(str.capitalize, state.split(' '))))
    
  url = f'https://api.covidactnow.org/v2/state/{state}.json?apiKey={covid_key}'
  try:
    return json.loads(requests.get(url).content.decode('utf-8'))
  except:
    return None


def get_molecule(molecule):
  base_url = f'https://cactus.nci.nih.gov/chemical/structure/{molecule}'
  data = {}
  
  data['image_url'] = f'{base_url}/image'
  data['mw'] = requests.get(f'{base_url}/mw').content.decode('utf-8')
  if 'Page not found (404)' in data['mw']:
    return None
  data['formula'] = requests.get(f'{base_url}/formula').content.decode('utf-8')
  data['rings'] = requests.get(f'{base_url}/ring_count').content.decode('utf-8')
  data['num_hydro_acc'] = requests.get(f'{base_url}/h_bond_acceptor_count').content.decode('utf-8')
  data['num_hydro_don'] = requests.get(f'{base_url}/h_bond_donor_count').content.decode('utf-8')

  return data


def get_roast():
  url = 'https://insult.mattbas.org/api/insult'
  return requests.get(url).content.decode('utf-8')


def get_amc_answer(url, key):
  val = amc10_answers.get(key)
  if val:
    return val
  
  page = requests.get(url)
  soup = BeautifulSoup(page.content, 'html.parser')
  results = soup.find(id='page-wrapper').find(id='main-content').find(id='main-column').find('div', class_='page-wrapper').find('div', class_='mw-body').find(id='mw-content-text').find('div', class_='mw-parser-output').find_all('p')

  op_2 = None
  op_3 = None
  for res in results:
    data = res.find_all('img', class_='latex')
    if len(data) > 0:
      for i in data:
        if 'boxed' in i['alt']:
          ans = i['alt']
          strs = re.findall('\((.*?)\)', ans)  
          for i in strs:
            if i in ('A', 'B', 'C', 'D', 'E'):
              amc10_answers[key] = i
              with open(amc10_answers_path, 'w') as f:
                f.write(yaml.dump(amc10_answers))
              return i
        elif 'box' in i['alt']:
          ans = i['alt']
          strs = re.findall('\{(.*?)\}', ans)
          for i in strs:
            if i in ('A', 'B', 'C', 'D', 'E'):
              op_2 = i
        elif 'extbf' in i['alt']:
          ans = i['alt']
          strs = re.findall('\((.*?)\)', ans)  
          for i in strs:
            if i in ('A', 'B', 'C', 'D', 'E'):
              op_3 = i

  if op_2 is None and op_3:
    amc10_answers[key] = op_3
    with open(amc10_answers_path, 'w') as f:
      f.write(yaml.dump(amc10_answers))
    return op_3

  amc10_answers[key] = op_2
  with open(amc10_answers_path, 'w') as f:
    f.write(yaml.dump(amc10_answers))
  return op_2  
        