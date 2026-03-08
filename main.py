import discord
from discord.ext import tasks, commands
import os
from dotenv import load_dotenv
import datetime
from pytz import timezone
from bs4 import BeautifulSoup
import requests
import urllib.parse
import time

data_samples = []
max_page = 100

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
HUKUYAKU_ID = os.getenv('HUKUYAKU_ID')
OHAYOU_ID = os.getenv('OHAYOU_ID')
KAKAKU_SSD = 'https://kakaku.com/pc/ssd/itemlist.aspx'
TARGET_URL = 'https://suumo.jp/jj/chintai/ichiran/FR301FC001/?ar=010&bs=040&ta=01&sc=01202&oz=01202109&sngz=&po1=12'
intents = discord.Intents.default()
intents.message_content = True
SSD_ID = os.getenv('SSD_ID')


#スクレイピング関数
def load_page(url):
    try:
        response = requests.get(url)
        response.raise_for_status() #エラーチェック
        
        soup = BeautifulSoup(response.content, 'html.parser')
        return soup
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        return None

def run_memory_scraping():
    # 価格昇順でソート (?pdf_so=p1)
    ssd_url = KAKAKU_SSD + '?pdf_so=p1&pn={}'
    
    targets = {
        '500GB': [],
        '512GB': [],
        '1000GB': [] # 1TB含む
    }
    
    # 3つのカテゴリが全て20件集まるか、ページ上限までループ
    for page in range(1, 11):
        if all(len(v) >= 20 for v in targets.values()):
            break
    
        #ページ情報
        current_page_url = ssd_url.format(page)
        soup = load_page(current_page_url)
        if soup is None:
            continue
            
        rows = soup.find_all('tr', class_='tr-border')
        for row in rows:
            try:
                name_tag = row.find(class_='ckitemLink')
                if not name_tag: continue
                name = name_tag.text.strip()
                
                price_tag = row.find(class_='yen')
                if not price_tag: continue
                price = price_tag.text.strip()
                
                link = name_tag.get('href')
                if link and not link.startswith('http'):
                    link = 'https://kakaku.com' + link

                item_info = f"{name} - {price}: {link}"
                
                # 容量判定 (商品名や行内のテキストで判定)
                row_text = row.text
                if ('1000GB' in name or '1TB' in name) and len(targets['1000GB']) < 20:
                    targets['1000GB'].append(item_info)
                elif '512GB' in name and len(targets['512GB']) < 20:
                    targets['512GB'].append(item_info)
                elif '500GB' in name and len(targets['500GB']) < 20:
                    targets['500GB'].append(item_info)
            except Exception:
                continue
                
    return targets
        

def run_scraping():
    local_data_samples = []
    url = TARGET_URL + '&pn={}'

    for page in range(1, max_page + 1):
        #ページ情報
        current_page_url = url.format(page)
        soup = load_page(current_page_url)
        if soup is None:
            continue
        #物件情報リストを指定
        mother = soup.find_all(class_='cassetteitem')
        
        #物件事の処理
        for child in mother:
            # 建物情報
            data_home = []
            # カテゴリ
            data_home.append(child.find(class_='ui-pct ui-pct--util1').text)
            # 建物名
            data_home.append(child.find(class_='cassetteitem_content-title').text)
            # 住所
            data_home.append(child.find(class_='cassetteitem_detail-col1').text)
            # 最寄り駅のアクセス
            children = child.find(class_='cassetteitem_detail-col2')
            for id,grandchild in enumerate(children.find_all(class_='cassetteitem_detail-text')):
                data_home.append(grandchild.text)
            # 築年数と階数
            children = child.find(class_='cassetteitem_detail-col3')
            for grandchild in children.find_all('div'):
                data_home.append(grandchild.text)

            # 部屋情報
            rooms = child.find(class_='cassetteitem_other')
            for room in rooms.find_all(class_='js-cassette_link'):
                data_room = []
                
                # 部屋情報が入っている表を探索
                for id_, grandchild in enumerate(room.find_all('td')):
                    # 階
                    if id_ == 2:
                        data_room.append(grandchild.text.strip())
                    # 家賃と管理費
                    elif id_ == 3:
                        data_room.append(grandchild.find(class_='cassetteitem_other-emphasis ui-text--bold').text)
                        data_room.append(grandchild.find(class_='cassetteitem_price cassetteitem_price--administration').text)
                    # 敷金と礼金
                    elif id_ == 4:
                        data_room.append(grandchild.find(class_='cassetteitem_price cassetteitem_price--deposit').text)
                        data_room.append(grandchild.find(class_='cassetteitem_price cassetteitem_price--gratuity').text)
                    # 間取りと面積
                    elif id_ == 5:
                        data_room.append(grandchild.find(class_='cassetteitem_madori').text)
                        data_room.append(grandchild.find(class_='cassetteitem_menseki').text)
                    # url
                    elif id_ == 8:
                        get_url = grandchild.find(class_='js-cassette_link_href cassetteitem_other-linktext').get('href')
                        abs_url = urllib.parse.urljoin(current_page_url, get_url)
                        data_room.append(abs_url)
                # 物件情報と部屋情報をくっつける
                data_sample = data_home + data_room
                local_data_samples.append(data_sample)
        time.sleep(1)
    return local_data_samples

def get_rent_value(row):
    # 家賃はリストの後ろから7番目の要素（data_roomのindex 1）
    rent_str = row[-7]
    try:
        # "万円"を削除して数値に変換
        return float(rent_str.replace('万円', ''))
    except ValueError:
        # 数値変換できない場合は無限大として扱い、ソート順を最後にする
        return float('inf')

client = commands.Bot(command_prefix='!', intents=intents)

async def report_ssd_prices(channel):
    await channel.send('SSDの価格調査を開始します...')
    
    results = await client.loop.run_in_executor(None, run_memory_scraping)
    
    for cap, items in results.items():
        if not items:
            continue
        message = f"【{cap} 最安トップ20】\n"
        chunk = ""
        for item in items:
            line = item + "\n"
            if len(chunk) + len(line) > 1900:
                await channel.send(message + chunk)
                message = "" 
                chunk = line
            else:
                chunk += line
        if chunk:
            await channel.send(message + chunk)

@client.command()
async def scrape_memory(ctx):
    # コマンドを実行したチャンネルに結果を送信します
    await report_ssd_prices(ctx.channel)

@client.command()
async def scrape(ctx):
    await ctx.send('スクレイピングを開始します...')
    # ブロッキング処理をExecutorで実行
    results = await client.loop.run_in_executor(None, run_scraping)
    await ctx.send(f'スクレイピングが完了しました。取得件数: {len(results)}')
    
    if results:
        # 家賃で昇順ソートして上位10件を取得
        sorted_data = sorted(results, key=get_rent_value)
        top_10 = sorted_data[:10]
        
        message = "【最安物件トップ10】\n"
        for item in top_10:
            # 建物名(index 1), 家賃(index -7), URL(index -1)
            message += f"{item[1].strip()} - {item[-7]}: {item[-1]}\n"
        
        await ctx.send(message)

@client.event
async def on_ready():
    loop.start()

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if message.channel.id == int(HUKUYAKU_ID) and message.content == '飲んだ':
        await message.channel.send('えらい')
    
    await client.process_commands(message)

@tasks.loop(seconds=30)
async def loop():
    now = datetime.datetime.now(timezone('Asia/Tokyo')).strftime('%H:%M')
    if now == '06:30' or  now == '21:00':
        channel = client.get_channel(int(HUKUYAKU_ID))
        await channel.send('服薬の時間だ同志')
    elif now == '6:00':
        channel = client.get_channel(int(OHAYOU_ID))
        await channel.send('おはよう')
    
    if now == '12:00' or now == '21:00':
        channel = client.get_channel(int(SSD_ID))
        if channel:
            await report_ssd_prices(channel)

client.run(TOKEN)