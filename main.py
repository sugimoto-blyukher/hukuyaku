import discord
from discord.ext import tasks
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
HUKUYAKU_ID = os.getenv('HUKUYAKU_ID')
OHAYOU_ID = os.getenv('OHAYOU_ID')

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if message.content == '飲んだ':
        channel = client.get_channel(HUKUYAKU_ID)
        await message.channel.send('えらい')

@tasks.loop(seconds=60)
async def loop():
    now = datetime.now().strftime('%H:%M')
    if now == '6:30' or  now == '21:00':
        channel = client.get_channel(HUKUYAKU_ID)
        await channel.send('服薬の時間だ同志')
    elif now == '6:00':
        channel = client.get_channel('OHAYOU_ID')
        await channel.send('おはよう')


client.run(TOKEN)