import asyncio
import discord
from discord.utils import find
import firebase_admin
import threading

from firebase_admin import credentials
from firebase_admin import firestore
import os
import random
from apis import get_question, get_apod, get_earth_image, get_mars_image, get_covid_stats, get_molecule, get_roast, get_amc_answer
import yaml
import re
from time import sleep
from help_pages import help_pages
import datetime
import math
import json

# class Buttons(discord.ui.View):
#   def __init__(self) -> None:
#     super().__init__(timeout=None)
#     self.value = None
    
discord.opus.load_opus(f"{os.getcwd()}/config/sounds/libopus.so.0.8.0")
FFMPEG_PATH = f'{os.getcwd()}/node_modules/ffmpeg-static/ffmpeg'
creds_path = 'config/creds.json'
help_embed_desc = "Hello, {}!\n\nSci Bowl Bot has a multitude of commands, as follows:\n\n__**Intellectual**__:\n\n**.q**: get asked a science bowl question\n**.a**: answer a science bowl question\n**.amc10**: get asked a random AMC 10 problem\n**.aamc10**: answer an AMC 10 question\n\n__**Monetary**__:\n\n**.lb**: view this server's leaderboard\n**.points**: view your points\n**.items**: view your items\n**.shop**: view a selection of buyable items\n**.purchase**: buy an item displayed in the shop\n**.daily**: collect your daily 200 points! If you do this regularly, the amount will increase from 200\n\n__**Fun**__\n\n**.flex**: Roast someone! Only possible with a **flex pass**\n**.apod**: view the astronomy picture of the day\n**.earth**: view a picture of Earth at a certain latitude/longitude\n**.mars**: view a random picture of Mars from a rover at a certain date\n**.molecule**: view information on a specific molecule\n**.covidstats**: get the COVID-19 statistics of a specific state\n\n__**Miscellaneous**__:\n\n**.help**: get help on our commmands\n**.skip**: Skip a question! Only possible with a **skip pass**\n\n__**Competitive**__:\n\nStill in development. We plan to have a Science Bowl competition portion of the bot, which includes real-time scoring and buzzing.\n\nThank you!"
# view=Buttons()
# view.add_item(discord.ui.Button(label="Invite",style=discord.ButtonStyle.link,url="https://google.com"))
with open('config/items.yml', 'r') as file:
  item_rarities = yaml.safe_load(file) 
with open('config/shop.yml', 'r') as file:
  shop_items = yaml.safe_load(file)
with open('config/randoms.yml', 'r') as file:
  randoms = yaml.safe_load(file)
with open('config/emojis.yml', 'r') as file:
  emojis = yaml.safe_load(file)

shop_embed_desc = 'Weclome to the **Shop**!\n\n__**Items For Sale**__:\n'
num = 1
for item, price in shop_items.items():
  shop_embed_desc += f'\n\t{num}. **{item}** for **{price:,}** points'
  num += 1
shop_embed_desc += '\n\nUse **.purchase** to buy the items listed in the **shop**.'
shop_embed = discord.Embed(
  title='Shop',
  colour=discord.Colour.blue(),
  description=shop_embed_desc
)


cred = credentials.Certificate(creds_path)
firebase_admin.initialize_app(cred)
db = firestore.client()

intents = discord.Intents.default()
intents.typing = True
intents.presences = True
intents.message_content = True
intents.members = True
client = discord.Client(intents=intents)
        

def comp_exists(channel_id):
  doc = db.collection('competition').document(channel_id).get()
  if not doc.exists:
    return False
  if doc.exists:
    if doc.to_dict().get('competition') == False:
      return False
  return True


def check_ban(user_id):
    doc = db.collection('users').document(str(user_id)).get()
    if not doc.exists:
      return True

    data = doc.to_dict()
    if data.get('banned') is None:
      return False
    return True

  
def increment_questions(user_id, guild_id):
  doc = db.collection('users').document(str(user_id)).get()
  if not doc.exists:
    guilds = [guild_id]
    db.collection('users').document(str(user_id)).set(
      {
        'points': 0,
        'guilds': guilds,
        'items': {'New Player Badge': 1},
        'questions_answered': 1,
        'last_daily': None,
        'daily_streak': 0
      }
    )
    
  else:
    ref = db.collection('users').document(str(user_id))
    ref.update({'questions_answered': firestore.Increment(1)})




def add_item(user_id, item_name, guild_id, quantity=1):
  ref = db.collection('users').document(str(user_id))
  doc = ref.get()
  if not doc.exists:
    guilds = [guild_id]
    db.collection(u'users').document(str(user_id)).set(
      {
        'points': 0,
        'guilds': guilds,
        'items': {'New Player Badge': 1, item_name: 1},
        'questions_answered': 0,
        'daily_streak': 0,
        'last_daily': None
      }
    )
    return None
  else:
    info = doc.to_dict()
    guilds = info['guilds']
    if guild_id not in guilds:
      guilds.append(guild_id)
    user_items = info['items']
    if user_items.get(item_name) is None:
      user_items[item_name] = quantity
    else:
      user_items[item_name] = user_items[item_name] + quantity

    ref.update({'items': user_items, 'guilds': guilds})
    return user_items

  
def add_points(user_id, additional_points, guild_id, multiplier=False, daily=0):
  doc = db.collection(u'users').document(str(user_id)).get()
  if not doc.exists:
    guilds = [guild_id]
    db.collection(u'users').document(str(user_id)).set(
      {
        'points': additional_points,
        'guilds': guilds,
        'items': {'New Player Badge': 1},
        'questions_answered': 0,
        'last_daily': datetime.datetime.utcnow(),
        'daily_streak': daily
      }
    )
    return additional_points
    
  else:
    info = doc.to_dict()
    points = info['points']
    guilds = info.get('guilds')
    items = info.get('items')
    last_daily = info.get('last_daily')
    questions_answered = info.get('questions_answered')
    if guilds is None:
      guilds = [guild_id]
    if guild_id not in guilds:
      guilds.append(guild_id)

  if multiplier is True:
    if 'Point Doubler' in info['items'].keys():
      additional_points *= 2
    if 'Point Tripler' in info['items'].keys():
      additional_points *= 3

  points += additional_points
  db.collection(u'users').document(str(user_id)).set(
    {
      'points': points,
      'guilds': guilds,
      'items': items,
      'questions_answered': questions_answered,
      'last_daily': last_daily,
      'daily_streak': info.get('daily_streak')
    }
  )

  return points


def update_current_questions(channel_id, question, answer, format):
  db.collection('questions').document(str(channel_id)).set(
    {
      'question': question,
      'answer': answer,
      'format': format
    }
  )


async def message_time_out(message, answer):
  await asyncio.sleep(20)
  c_id = str(message.channel.id)
  ref = db.collection('questions').document(c_id)
  doc = ref.get()
  if not doc.exists:
    return
  info = doc.to_dict()
  if info['question'] == message.content:
    ref.delete()
    await message.channel.send(f'\n\nQuestion **timed out**. Go faster next time! The correct answer was **{answer}**')


async def amc_time_out(solution, channel, contest='10'):
  try:
    prob = int(solution[len(solution) - 2:])
  except ValueError:
    prob = int(solution[len(solution) - 2:][1:])
  if prob in range(1, 11):
    sleep_time = 300
  elif prob in range(11, 21):
    sleep_time = 450
  else:
    sleep_time = 600
  
  await asyncio.sleep(sleep_time)
  c_id = str(channel.id)
  ref = db.collection(f'AMC {contest}').document(c_id)
  doc = ref.get()
  if not doc.exists:
    return
  info = doc.to_dict()
  if info['solution'] == solution:
    ref.delete()
    correct = info['answer']
    solution = info['solution']
    await channel.send(f'\n\nAMC {contest} question **timed out**. Go faster next time! The correct answer was **{correct}**.\n\nTo view a more detailed solution, visit <{solution}>')


async def luck(user, chan, guild_id, type='.a'):
  r = random.randint(1, 5)
  if r == 1:
    item = randoms[type][random.randint(0, len(randoms[type]) - 1)]
    add_item(user.id, item, guild_id)
    await chan.send(f"<@{user.id}> You lucked out! You found a {item} while answering the question!")


def get_amc_question(year, question, test='10'):
  r = random.randint(1, 2)
  if r == 1:
    k = 'A'
  elif r == 2:
    k = 'B'
  
  if question == '':
    question = f"{random.randint(1, 25)}.png"
  elif question in range(1, 26):
    question = f"{question}.png"
  else:
    return None

  path = f'{os.getcwd()}/config/amc_questions/amc{test}'
  if year == '':
    year = random.choice(
      os.listdir(path)
    )
    img = f"{path}/{year}/{k}/{question}"
  elif 'A' not in year.upper() and 'B' not in year.upper():
    img = f"{path}/{year}/{k}/{question}"
  else:
    img = f"{path}/{year[:-1]}/{year[-1]}/{question}"

  return img



@client.event
async def on_guild_join(guild):
  help_embed = discord.Embed(
    title='Sci Bowl Bot',
    colour=discord.Colour.blue(),
    description=help_embed_desc.format(guild.name)
  )
  general = find(lambda x: 'general' in x.name.lower().strip(),  guild.text_channels)
  if general and general.permissions_for(guild.me).send_messages:
    await general.send(embed=help_embed)

  ritz = client.get_user(813841199496036414)
  pan = client.get_user(836361597701193748)
  integrations = await guild.integrations()
  bot_inviter = None
  
  for integration in integrations:
    if isinstance(integration, discord.BotIntegration):
      if integration.application.user.name == client.user.name:
        bot_inviter = str(integration.user)

  em = discord.Embed(
    title='Sci Bowl Bot got added to a guild!',
    description=f"Name: **{guild.name}**\nID: {guild.id}\nInviter: **{bot_inviter}**",
    colour=discord.Colour.blue()
  )
  await ritz.send(embed=em)
  await pan.send(embed=em)


@client.event
async def on_ready():
  await client.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=".help!"))
  print(f"{client.user} is online!")
  

@client.event
async def on_message(message):
  if message.author == client.user:
    return

  elif isinstance(message.channel, discord.channel.DMChannel):
    return await message.channel.send(f'Hi **{message.author}**!\n\nSci Bowl Bot currently does not support commands in DMs, since Sci Bowl Bot is intended to invoke competition between peers. To use the bot (or to get help), join this server:\n\nhttps://discord.gg/U69UrDNbsn')

  elif message.content == '.ping':
    return await message.channel.send(f"<@{message.author.id}> **{round(client.latency * 1000):,}** ms")
  
  elif message.content[:5] == '.help':
    data = message.content.strip().split()
    if len(data) == 1:
      help_embed = discord.Embed(
        title='Sci Bowl Bot',
        colour=discord.Colour.blue(),
        description=help_embed_desc.format(message.author.name)
      )
      return await message.channel.send(embed=help_embed)

    cmd = data[1].strip('.')
    desc = help_pages.get(cmd)
    if desc is None:
      return await message.channel.send('Currently, we do not have a help page for that command')
      
    em = discord.Embed(
      title=f'Help ({data[1]})',
      colour=discord.Colour.blue(),
      description=desc
    )
    await message.channel.send(embed=em)

  elif message.content.strip().lower() == '.daily':
    ref = db.collection('users').document(
      str(message.author.id)
    )
    doc = ref.get()
    if not doc.exists:
      add_points(
        message.author.id,
        200,
        message.guild.id,
        daily=1
      )
      return await message.channel.send(f"<@{message.author.id}> you just received **200** points for collecting your daily award!")

    info = doc.to_dict()
    if info.get('last_daily') is None:
      ref.update(
        {
          'last_daily': datetime.datetime.utcnow(),
          'daily_streak': 1
        }
      )
      add_points(
        message.author.id,
        200,
        message.guild.id
      )
      return await message.channel.send(f"<@{message.author.id}> you just received **200** points for collecting your daily award!")
      
    else:
      last_daily = datetime.datetime.strptime(
        str(info.get('last_daily'))[:-16],
        '%Y-%m-%d %H:%M'
      )
      now = datetime.datetime.utcnow()
      diff = now - last_daily
      days = diff.total_seconds() / 86400
      
      if days < 1:
        remaining = (1 - days) * 24
        hours = math.floor(remaining)
        minutes = round((remaining - hours) * 60)
        await message.channel.send(f"<@{message.author.id}> you've already claimed your daily today! Wait another {hours} hours and {minutes} minutes.")
      elif days >= 1 and days < 2:
        pts = math.floor(200 * (1 + (info.get('daily_streak') / 10)))
        await message.channel.send(f"<@{message.author.id}> you just received **{pts}** points for collecting your daily award! (Extra points are due to your **{info.get('daily_streak')}**-day long streak)")
        add_points(
          message.author.id,
          pts,
          message.guild.id
        )
        ref.update(
          {
            'last_daily': datetime.datetime.utcnow(),
            'daily_streak': firestore.Increment(1)
          }
        )
      else:
        await message.channel.send(f"<@{message.author.id}> you just received **200** points for collecting your daily award! Sadly, you lost your daily streak :(")
        add_points(
          message.author.id,
          200,
          message.guild.id
        )
        ref.update(
          {
            'last_daily': datetime.datetime.utcnow(),
            'daily_streak': 1
          }
        )

  elif message.content[:6] == '.amc10':
    ref = db.collection('AMC 10').document(str(message.channel.id))
    doc = ref.get()
    if doc.exists:
      return await message.channel.send('There is an active AMC 10 question in this channel')
    
    data = message.content.split()
    if len(data) == 3:
      year = data[1].upper()
      question = data[2]
      try:
        question = int(question)
      except:
        pass
    elif len(data) == 2:
      year = data[1]
      question = ''
    elif len(data) == 1:
      year = ''
      question = ''
    else:
      return await message.channel.send('Invalid command!')

    if year.lower() == 'x':
      year = ''

    p = get_amc_question(
      year,
      question
    )
    data = p.split('/')

    ex = data[-2]
    year = data[-3]
    prob = data[-1][:-4]
    
    contest = f'AMC 10{ex} {year} Problem #{prob}'
    sol_link = f"https://aops.com/wiki/index.php/{year}_AMC_10{ex}_Problems/Problem_{prob}"
    try:
      ref.set(
        {
          'solution': sol_link,
          'answer': get_amc_answer(
            sol_link,
            f"10{ex}:{year}:{prob}"
          )
        }
      )
      await message.channel.send(f"<@{message.author.id}> {contest}", file=discord.File(p))
      asyncio.create_task(amc_time_out(sol_link, message.channel))
    except FileNotFoundError:
      await message.channel.send('Invalid AMC 10 competition')

  elif message.content[:7] == '.aamc10':
    ref = db.collection(
      'AMC 10'
    ).document(str(message.channel.id))
    doc = ref.get()
    if not doc.exists:
      return await message.channel.send('There is no AMC 10 question in this channel')
      
    ans = message.content[8].upper()
    info = doc.to_dict()
    correct = info['answer']
    solution = info['solution']
    increment_questions(
      message.author.id,
      message.guild.id
    )
    if ans == correct:
      points = add_points(                  
        message.author.id,
        20,
        message.guild.id,
        multiplier=True
      )
      ref.delete()
      await message.channel.send(f'Correct! Good job, **{str(message.author)[:-5]}**. You now have **{points:,}** points!')
      return await luck(
        message.author,
        message.channel,
        message.guild.id,
        type='.aamc10'
      )
      
    else:
      points = add_points(
        message.author.id,
        -5,
        message.guild.id
      )
      
      ref.delete()
      return await message.channel.send(f"Wrong! Get better, **{str(message.author)[:-5]}**. The correct answer was **{correct}**. You now have **{points:,}** points.\n\nTo view a more detailed solution, visit <{solution}>")
    
  elif message.content == '.shop':
    await message.channel.send(embed=shop_embed)

  elif message.content[:9] == '.purchase' or message.content[:4] == '.buy':
    try:
      quantity = int(message.content.split()[-1])
      item = ' '.join(message.content.split()[1:-1])
      if quantity < 1:
        return await message.channel.send('Enter a whole number!')
    except:
      try:
        float(message.content.split()[-1])
        return await message.channel.send('Enter a whole number!')
      except:
        item = ' '.join(message.content.split()[1:])
        quantity = 1

    if item.lower() == 'doe autograph':
      item = 'DOE Autograph'
    elif item.lower().startswith('air force'):
      item = "Air Force One's"
    else:
      item = ' '.join(map(str.capitalize, item.split(' ')))
    if item not in shop_items.keys():
      await message.channel.send('Item not purchasable')
      return

    cost = shop_items[item] * quantity
    points_before = add_points(message.author.id, 0, message.guild.id)
    if points_before < cost:
      return await message.channel.send("You don't have enough coins!")
    points_now = add_points(message.author.id, cost * -1 * quantity, message.guild.id)
    add_item(message.author.id, item, message.guild.id, quantity=quantity)
    em = discord.Embed(
      title='Purchase Successful!',
      colour=discord.Colour.blue(),
      description=f"<@{message.author.id}> successfully purchased {quantity:,} **{item}** for **{cost:,}** points! You now have **{points_now:,}** points."
    )
    await message.channel.send(embed=em)

  elif message.content[:5] == '.flex':
    user_id = message.author.id
    ref = db.collection('users').document(str(user_id))
    doc = ref.get()
    if not doc.exists:
      return await message.channel.send("You don't have a flex pass!")
    info = doc.to_dict()
    if 'Flex Pass' not in info['items'].keys():
      return await message.channel.send("You don't have a flex pass!")
    elif not message.mentions:
      return await message.channel.send('Specify someone to flex on.')

    roasted_tag = str(message.mentions[0])[:-5]
    roast = get_roast()
    roast = roast[0].lower() + roast[1:]
    await message.channel.send(f"**{roasted_tag}**, {roast}")

  elif message.content[:6] == '.items':
    if message.content == '.items':
      u = message.author
    elif message.content[:6] == '.items' and message.mentions:
      u = message.mentions[0]
    else:
      return await message.channel.send('This user is not valid!')
      
    doc = db.collection('users').document(str(u.id)).get()
    if not doc.exists:
      db.collection('users').document(str(u.id)).set(
        {
          'points': 0,
          'guilds': [message.guild.id],
          'items': {'New Player Badge': 1},
          'questions_answered': 0,
          'last_daily': None,
          'daily_streak': 0
        }
      )
      em = discord.Embed(
        title=f"{str(u)[:-5]}'s Items",
        colour=discord.Colour.blue(),
        description=f"__**{item_rarities['New Player Badge']}**__:\n\t- **New Player Badge**: 1\n\n__**Points**__: 0"
      )
      await message.channel.send(embed=em)
      return

    info = doc.to_dict()
    items = info['items']
    items_final = {}
    for item, quantity in items.items():
      if item_rarities[item] not in items_final.keys():
        items_final[item_rarities[item]] = [{'item': item, 'quantity': quantity}]
      else:
        items_final[item_rarities[item]].append({'item': item, 'quantity': quantity})

    k = items_final.keys()
    for i in set(item_rarities.values()):
      if i not in k:
        items_final[i] = []

    ans = info['questions_answered']
    if ans > 0:
      items_final[item_rarities['Question-Answered Stickers']].append({'item': 'Question-Answered Stickers', 'quantity': ans})
    if ans >= 25:
      items_final[item_rarities['25-Questions-Answered Certificate']].append({'item': '25-Questions-Answered Certificate', 'quantity': ans // 25})
    if ans >= 50:
      items_final[item_rarities['50-Questions-Answered Certificate']].append({'item': '50-Questions-Answered Certificate', 'quantity': ans // 50})
    if ans >= 100:
      items_final[item_rarities['100-Questions-Answered Certificate']].append({'item': '100-Questions-Answered Certificate', 'quantity': ans // 100})
    if ans >= 250:
      items_final[item_rarities['250-Questions-Answered Certificate']].append({'item': '250-Questions-Answered Certificate', 'quantity': ans // 250})
    if ans >= 500:
      items_final[item_rarities['500-Questions-Answered Certificate']].append({'item': '500-Questions-Answered Certificate', 'quantity': ans // 500})
    if ans >= 1000:
      items_final[item_rarities['1000-Questions-Answered Certificate']].append({'item': '1000-Questions-Answered Certificate', 'quantity': ans // 1000})

    desc = ''
    for rarity, values in items_final.items():
      if len(values) == 0:
        continue
      desc += f"__**{rarity}**__:\n"
      for num, i in enumerate(values):
        ej = emojis.get(i['item'])
        if ej is None:
          ej = ''
        else:
          ej = f" {ej}"
        desc += f"\t- **{i['item']}**{ej}: {i['quantity']}"
        if num != len(values) - 1:
          desc += '\n'
      desc += '\n\n'
    desc += f"__**Points**__: {info['points']:,}"

    em = discord.Embed(
        title=f"{str(u)[:-5]}'s Items",
        colour=discord.Colour.blue(),
        description=desc
    )
    await message.channel.send(embed=em)

  elif message.content[:9] == '.molecule':
    molecule = message.content[10:]
    data = get_molecule(molecule)
    if data is None:
      await message.channel.send('No such molecule!')
      return
      
    embed = discord.Embed(
      title=molecule,
      colour=discord.Colour.blue(),
      description=f"**Formula**: {data['formula']}\n**Number of Rings**: {data['rings']}\n**Number of Hydrogen Acceptors**: {data['num_hydro_acc']}\n**Number of Hydrogen Donors**: {data['num_hydro_don']}"
    )
    embed.set_image(url=data['image_url'])
    try:
      await message.channel.send(embed=embed)
    except discord.errors.HTTPException:
      await message.channel.send('No such molecule!')

  elif message.content[:11] == '.covidstats':
    state = message.content[12:]    
    data = get_covid_stats(state)
    if data is None:
      await message.channel.send('No such state!')
      return

    population = data['population']
    pos_perc = data['metrics']['testPositivityRatio'] * 100
    new_per_100 = data['metrics']['weeklyNewCasesPer100k']
    vacc_perc = data['metrics']['vaccinationsCompletedRatio'] * 100
    embed = discord.Embed(
      title=f'COVID-19 Statistics for {state}',
      colour=discord.Colour.blue(),
      description=f'Population: **{population:,}**\nPercent of Tests That Are Positive: **{pos_perc}%**\nWeekly New Cases Per 100K: **{new_per_100}**\nPercent of Population Fully Vaccinated: **{vacc_perc}%**'
    )
    await message.channel.send(embed=embed)

  elif message.content == '.apod':
    data = get_apod()
    embed = discord.Embed(
      title="Astronomy Picture of the Day!",
      colour=discord.Colour.blue(),
      description=f'"**{data["title"]}**":\n\n{data["explanation"]}**'
    )
    embed.set_image(url=data['url'])

    await message.channel.send(embed=embed)

  elif message.content[:5] == '.mars':
    try:
      date = message.content.split()[1]
    except:
      await message.channel.send('Invalid Date!')
      return

    photos = get_mars_image(date)
    if photos is None:
      return await message.channel.send('Put your date in the format YYYY-MM-DD')
    elif len(photos) == 0:
      return await message.channel.send('No available photos!')
      
    photo_url = photos[random.randint(0, len(photos) - 1)]['img_src']
    embed = discord.Embed(
      title=f"Mars on {date}!",
      colour=discord.Colour.blue()
    )
    embed.set_image(url=photo_url)

    await message.channel.send(embed=embed)

  elif message.content[:6] == '.earth':
    inp = message.content.split()
    lat = float(inp[1])
    long = float(inp[2])
    data = get_earth_image(lat, long)
    
    embed = discord.Embed(
      title=f'Earth at ({lat}, {long})!',
      colour=discord.Colour.blue()
    )
    try:
      embed.set_image(url=data['url'])
    except:
      await message.channel.send('Invalid coordinates!')
      return
    
    await message.channel.send(embed=embed)
    
  elif message.content[:2] == '.q':
    ref = db.collection('questions').document(str(message.channel.id))
    if ref.get().exists:
      return await message.channel.send('There is an active question in this channel.')
    
    subj = message.content[3:].lower().strip()
    if subj == 'bio':
      question, answer, format = get_question('BIOLOGY')
    elif subj == 'chem':
      question, answer, format = get_question('CHEMISTRY')
    elif subj == 'gen sci' or subj == 'gensci':
      question, answer, format = get_question('GENERAL SCIENCE')
    elif subj == 'phys' or subj == 'phy':
      question, answer, format = get_question('PHYSICS')
    elif subj == 'cs':
      question, answer, format = get_question('COMPUTER SCIENCE')
    elif subj == 'astro':
      question, answer, format = get_question('ASTRONOMY')
    elif subj == 'es':
      question, answer, format = get_question('EARTH SCIENCE')
    elif subj == 'energy':
      question, answer, format = get_question('ENERGY')
    elif subj == 'math':
      question, answer, format = get_question('MATH')
    else:
      question, answer, format = get_question()

    update_current_questions(message.channel.id, question, answer, format)
    m = await message.channel.send(question)
    asyncio.create_task(message_time_out(m, answer))

  elif message.content[:3] == '.a ':
    ref = db.collection('questions').document(str(message.channel.id))
    doc = ref.get()
    if not doc.exists:
      return await message.channel.send('There is no active question in this channel!')

    else:
      answer = message.content[3:]
      question_info = doc.to_dict()
      increment_questions(message.author.id, message.guild.id)

      if question_info['format'] == 'Short Answer':
        if answer.lower().strip() == question_info['answer'].lower().strip():
          points = add_points(message.author.id, 5, message.guild.id, multiplier=True)
          await message.channel.send(f'Correct! Good job, **{str(message.author)[:-5]}**. You now have **{points:,}** points!')
          await luck(message.author, message.channel, message.guild.id)
        elif 'ACCEPT' in question_info['answer']:
          accepted = question_info['answer'][question_info['answer'].find('(') + 1:question_info['answer'].find(')')]
          accepted = accepted[8:]
          if answer.lower().strip() == accepted.lower().strip():
            points = add_points(message.author.id, 5, message.guild.id, multiplier=True)
            await message.channel.send(f'Correct! Good job, **{str(message.author.name)}**. You now have **{points:,}** points!')
            await luck(message.author, message.channel, message.guild.id)
          else:
            points = add_points(message.author.id, -3, message.guild.id)
            await message.channel.send(f"Wrong! Get better, **{str(message.author.name)}**. The correct answer was **{question_info['answer']}**. You now have **{points:,}** points.")
        elif '(' in answer and ')' in answer:
          new = re.sub("[\(\[].*?[\)\]]", "", answer).strip().lower()
          if question_info['answer'].strip().lower() == new:
            points = add_points(message.author.id, 5, message.guild.id, multiplier=True)
            await message.channel.send(f'Correct! Good job, **{str(message.author.name)}**. You now have **{points:,}** points!')
            await luck(message.author, message.channel, message.guild.id)
          else:
            points = add_points(message.author.id, -3, message.guild.id)
            await message.channel.send(f"Wrong! Get better, **{str(message.author.name)}**. The correct answer was **{question_info['answer']}**. You now have **{points:,}** points. ")
        else:
          points = add_points(message.author.id, -3, message.guild.id)
          await message.channel.send(f"Wrong! Get better, **{str(message.author.name)}**. The correct answer was **{question_info['answer']}**. You now have **{points:,}** points. ")
          
      elif question_info['format'] == 'Multiple Choice':
        if answer.lower().strip() == question_info['answer'][0].lower().strip():
          points = add_points(message.author.id, 5, message.guild.id, multiplier=True)
          await message.channel.send(f'Correct! Good job, **{str(message.author.name)}**. You now have **{points:,}** points!')
          await luck(message.author, message.channel, message.guild.id)
        else:
          points = add_points(message.author.id, -3, message.guild.id)
          await message.channel.send(f"Wrong! Get better, **{str(message.author.name)}**. The correct answer was **{question_info['answer']}**. You now have **{points:,}** points.")

      ref.delete()
    
  elif message.content == ".points":
    if not message.mentions:
      points = add_points(message.author.id, 0, message.guild.id)
      return await message.channel.send(f'{message.author.name} has **{points:,}** points!')

    points = add_points(message.mentions[0].id, 0, message.guild.id)
    return await message.channel.send(f'{message.mentions[0]} has **{points:,}** points!')
    
  elif message.content == ".leaderboard" or message.content == '.lb':
    docs = db.collection('users').where(
      'guilds',
      'array_contains',
      message.guild.id
    ).order_by(
      'points',
      direction=firestore.Query.DESCENDING
    ).stream()

    description = ''
    esc = 1
    for num, doc in enumerate(docs):
      u = client.get_user(int(doc.id))
      if u is None:
        esc -= 1
        continue
      tag = str(u)
      pts = doc.to_dict().get('points')
      description += f"**{num + esc}.** {tag}: **{pts:,}** Points\n"
      
    em = discord.Embed(
      title=f"{message.guild.name}'s Leaderboard!",
      colour=discord.Colour.blue(),
      description=description
    )
    
    await message.channel.send(embed=em)
    
  elif message.content[:8] == '.devgive':
    if message.author.id != 813841199496036414 and message.author.id != 836361597701193748:
      return await message.channel.send("You don't have permission to run that command!")

    if not message.mentions:
      return await message.channel.send('Mention someone to give points to!')

    try:
      mention = message.mentions[0]
      pts = int(message.content.split()[1])
      add_points(mention.id, pts, message.guild.id)
      return await message.channel.send(f'Added **{pts:,}** points to **{mention}**!')
    except ValueError:
      return await message.channel.send('Invalid number!')

  elif message.content.startswith('.devget'):
    if message.author.id not in (813841199496036414, 836361597701193748):
      return await message.channel.send("You don't have permission to run that command!")

    if not message.mentions:
      return await message.channel.send('Mention someone to give points to!')

    user_id = message.mentions[0].id
    doc = db.collection('users').document(str(user_id)).get()
    if doc.exists:
      data = doc.to_dict()
      data['last_daily'] = str(data.get('last_daily'))
      await message.channel.send(f"Data:\n\n{json.dumps(data, indent=4)}")
    else:
      await message.channel.send('No such user!')

  elif message.content == '.skip':
    user_id = message.author.id
    ref = db.collection('users').document(str(user_id))
    doc = ref.get()
    if not doc.exists:
      return await message.channel.send("You don't have a skip pass!")
    info = doc.to_dict()
    if 'Skip Pass' not in info['items'].keys():
      return await message.channel.send("You don't have a skip pass!")

    ref = db.collection('questions').document(str(message.channel.id))
    if ref.get().exists:
      ref.delete()
      await message.channel.send('Question skipped!')
    else:
      await message.channel.send('There is no question to skip!')
      
  elif message.content[:11] == ".startcomp":
    def check(newmsg):
      if newmsg.author == message.author and newmsg.channel == message.channel:
        return True
      else:
        return False
    
    if comp_exists(str(message.channel.id)) == True:
      return await message.channel.send("There is already an ongoing competition.")
    
    await message.channel.send("Enter the amount of teams you want in your game:")
    
    def team_check(new_msg):
      if new_msg.author == message.author and new_msg.channel == message.channel:
        return True
      else:
        return False
      
    msg = await client.wait_for('message', check=team_check)
    try:
      team_count = int(msg.content)
      if team_count > 30:
        return await message.channel.send("The number of teams can't be more than 30")
      try:
        await message.channel.send("Enter the name of the voice channel in which you will play this game (use dashes if needed):")
        vcmsg = await client.wait_for('message', check=check)
        channel = discord.utils.get(message.guild.channels, name=vcmsg.content, type=discord.ChannelType.voice) 
        await channel.connect()
        await message.channel.send(f"Connected! Please join <#{channel.id}> and wait for the game to begin...")
        team_list = []
        for i in range(team_count):
          team_list.append(0)
          db.collection('competition').document(str(message.channel.id)).set(
          {
            'competition': True,
            'teams': team_count,
            'teamlist': team_list,
            'moderator': message.author.id,
            'vc': channel.name,
            'buzz': False,
          }
        )
        sleep(5)
        await message.channel.send("If everyone has joined the channel, the moderators may start the competition by reading the questions, and the players can run `.buzz` if they know the answer. This is not neccessary for bonuses. \n\nIf the player interrupts on a tossup, the moderator can run `.neg` and that player will be penalized\n\nIf the player gets the question correct, the moderator can run `.compadd <team number> t` for a tossup or `.compadd <team number> b` for a bonus.\n\nThe game has now begun!")
      except Exception as e:
        if e == "Already connected to a voice channel.":
            return await message.channel.send("There is another ongoing competition. Please wait for that to end before starting a new one.")
        print(e)
        return await message.channel.send('Invalid voice channel.')
    except:
      return await message.channel.send("Your response has to be a number")
          
  elif message.content == ".endcomp":
    if comp_exists(str(message.channel.id)) == False:
      return await message.channel.send("There is no ongoing competition.")
    doc = db.collection('competition').document(str(message.channel.id)).get().to_dict()
    winning_team = max(doc['teamlist'])
    channel = message.guild.voice_client
    await message.channel.send(f"The competition has ended, with the winner being **Team {doc['teamlist'].index(winning_team) + 1}** with **{winning_team}** points!")
    await channel.disconnect()
    db.collection('competition').document(str(message.channel.id)).set(
      {
        'competition': False,
        'teams': 0,
        'teamlist': [],
        'moderator': 0,
        'vc': "",
        'buzz': False,
      }
    )
    
  elif message.content.startswith(".compadd"):
    if comp_exists(str(message.channel.id)) == False:
      return await message.channel.send("There is no ongoing competition.")
    data = message.content.split()
    teamnum = 0
    try:
      teamnum = int(data[1])
    except:
      return await message.channel.send("You have not entered a valid response.")
    torb = data[2]
    doc = db.collection('competition').document(str(message.channel.id)).get().to_dict()
    if doc['moderator'] != message.author.id:
      return await message.channel.send("You are not the moderator of this game.")
    teamlist = doc['teamlist']
    if torb == "t":
      teamlist[teamnum - 1] += 4
      await message.delete()          
      db.collection('competition').document(str(message.channel.id)).set(
        {
          'competition': True,
          'teams': doc['teams'],
          'teamlist': teamlist,
          'moderator': doc['moderator'],
          'vc': doc['vc'],
          'buzz': False,
        }
      )
    elif torb == "b":
      teamlist[teamnum - 1] += 10
      await message.delete()
      db.collection("competition").document(str(message.channel.id)).set(
        {
          'competition': True,
          'teams': doc['teams'],
          'teamlist': teamlist,
          'moderator': doc['moderator'],
          'vc': doc['vc'],
          'buzz': False,
        }
      )
    else:
      return await message.channel.send("You have not entered a valid response.")
        
  elif message.content == ".scorecheck":
    if comp_exists(str(message.channel.id)) == False:
      return await message.channel.send("There is no ongoing competition.")
    doc = db.collection('competition').document(str(message.channel.id)).get().to_dict()
    if doc['moderator'] != message.author.id:
      return await message.channel.send("You are not the moderator of this game.")
    scorestring = ""
    for i in range(doc['teams']):\
       scorestring += f"**Team {i + 1}** has **{doc['teamlist'][i]}** points.\n\n"
    await message.channel.send(scorestring)
    
  elif message.content == ".buzz":
    if comp_exists(str(message.channel.id)) == False:
      return await message.channel.send("There is no ongoing competition.")
    doc = db.collection('competition').document(str(message.channel.id)).get().to_dict()
    
    if doc['moderator'] == message.author.id:
      return await message.channel.send("The moderator cannot buzz in.")
    if (doc['buzz']) == True:
      return await message.channel.send("Someone has already buzzed in.")
    ref = db.collection("competition").document(str(message.channel.id))
    ref.set(
      {
        'competition': True,
        'teams': doc['teams'],
        'teamlist': doc['teamlist'],
        'moderator': doc['moderator'],
        'vc': doc['vc'],
        'buzz': True
      }
    )
    await message.channel.send("Buzz!")
    voice_client = message.guild.voice_client
    channel = voice_client.play(discord.FFmpegPCMAudio(executable=FFMPEG_PATH, source=f'{os.getcwd()}/config/sounds/buzz.mp3'))
    
  elif message.content == ".reset":
    if comp_exists(str(message.channel.id)) is False:
      return await message.channel.send("There is no ongoing competition.")
    doc = db.collection('competition').document(str(message.channel.id)).get().to_dict()
    if doc['moderator'] != message.author.id:
      return await message.channel.send("You are not the moderator.")
    if (doc['buzz']) == False:
      return await message.channel.send("There is no current buzz!")
      
    ref = db.collection("competition").document(str(message.channel.id))
    ref.update(
      {
        'competition': True,
        'buzz': False
      }
    )
      
      
if __name__ == '__main__':
  while True:
    try:
      client.run(os.environ['BOT_TOKEN'])
    except discord.errors.HTTPException:
      os.system('kill 1')