import discord
from discord.ext import commands
from discord.ui import View, Button
import random
import requests
from PIL import Image, ImageDraw, ImageFont
import datetime
import asyncio
import tweepy
from dotenv import load_dotenv
import threading
import logging
import os
from flask import Flask

# === Загрузка переменных окружения ===
load_dotenv()

# === Переменные окружения ===
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
TWITTER_USER_ID = os.getenv("TWITTER_USER_ID")
TWITTER_USERNAME = 'Red_Planet_Dao'        # имя пользователя

GUILD_ID = 1249275519716036679             # Сервер Discord
BTC_CHANNEL_ID = 1251146452223131812       # Канал, где меняется имя
TWITTER_CHANNEL_ID = 1249287351684038727   # Канал, куда отправляются твиты

# === Инициализация Discord бота ===
intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = True  # если планируется обработка текста сообщений
bot = commands.Bot(command_prefix='/', intents=intents)
tree = bot.tree  # для слеш-команд

# === Путь к ресурсам ===
background_path = "background.jpg"   # путь к фоновому изображению
font_path = "SpicyRice-Regular.ttf"  # путь к шрифту

# === Твиттер клиент ===
twitter_client = tweepy.Client(bearer_token=BEARER_TOKEN)  # авторизация Twitter

# === Проверка переменных окружения ===
missing_vars = []
if not DISCORD_TOKEN: missing_vars.append("DISCORD_TOKEN")
if not GUILD_ID: missing_vars.append("GUILD_ID")
if not BTC_CHANNEL_ID: missing_vars.append("BTC_CHANNEL_ID")
if not TWITTER_CHANNEL_ID: missing_vars.append("TWITTER_CHANNEL_ID")

if missing_vars:
    raise ValueError(f"❌ Не найдены переменные окружения: {', '.join(missing_vars)}")

# === HTTP Сервер (для Render) ===
app = Flask(__name__)
@app.route("/")
def index():
    return "Bot is running."

# === Настройка логирования ===
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("logs.txt", encoding="utf-8"),
        logging.StreamHandler()  # чтобы логи также выводились в консоль
    ]
)

# === Работа с файлами ===
PRICE_FILE = "last_price.txt"  # Запоминать последнюю цену BTC

def load_last_price():
    if os.path.exists(PRICE_FILE):
        with open(PRICE_FILE, "r") as f:
            try:
                return float(f.read().strip())
            except:
                return None
    return None

def save_last_price(price):
    with open(PRICE_FILE, "w") as f:
        f.write(str(price))

LAST_TWEET_FILE = "last_tweet.txt"  # Запоминать последний отправленный твит

def load_last_tweet_id():
    if os.path.exists(LAST_TWEET_FILE):
        with open(LAST_TWEET_FILE, "r") as f:
            return f.read().strip()
    return None

def save_last_tweet_id(tweet_id):
    with open(LAST_TWEET_FILE, "w") as f:
        f.write(str(tweet_id))

last_tweet_id = load_last_tweet_id()  # Храним предыдуший твит
previous_price = load_last_price()    # Храним предыдущую цену
seen_tweet_ids = set()

# === Получение цены BTC ===
async def get_btc_price():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
    response = requests.get(url)
    data = response.json()
    return round(data["bitcoin"]["usd"], 2)

# === Обновление имени канала BTC ===
async def update_btc_channel_name():
    global previous_price
    try:
        current_price = await get_btc_price()
        guild = bot.get_guild(GUILD_ID)
        if guild is None:
            logging.error("❌ Guild not found.")
            return
        channel = guild.get_channel(BTC_CHANNEL_ID)
        if not channel:
            logging.error(f"❌ [BTC] Канал с ID {BTC_CHANNEL_ID} not found.")
            return

        if previous_price is not None:
            if current_price > previous_price:
                emoji = "🟢⬈"  # зелёный кружок и стрелка вверх
                color = "зелёный"
            elif current_price < previous_price:
                emoji = "🔴⬊"  # красный кружок и стрелка вниз
                color = "красный"
            else:
                emoji = "⚪"
                color = "белый"
        else:
            emoji = "🟡"
            color = "жёлтый (первая загрузка)"

        new_name = f"{emoji} BTC: $ {current_price}"
        await channel.edit(name=new_name)
        logging.info(f"Цена BTC: ${new_name} ({color})")
        previous_price = current_price
        save_last_price(current_price)
    except Exception as e:
        logging.error(f"[BTC] Ошибка при обновлении: {e}")
        
    # Обработка ошибки 429
    except discord.errors.HTTPException as e:
        if e.status == 429:
            logging.warning("[DISCORD] Rate limit: слишком частое обновление канала.")
        else:
            logging.error(f"[DISCORD] Ошибка при изменении имени канала: {e}")

# === Генерация изображения ===
def create_price_image(price):
    # Загрузка фонового изображения
    img = Image.open(background_path)
    draw = ImageDraw.Draw(img)
    text = f"BTC\n${price}"
    
    # Настройка шрифта
    font = ImageFont.truetype(font_path, 140)
    
    x, y = 35, 20  # Позиция текста
    
    # Цвета
    main_color = (255, 0, 0)          # красный основной текст
    shadow_color = (0, 0, 0)          # чёрная тень
    outline_color = (255, 215, 0)     # золотой контур

    # Рисуем ТЕНЬ (смещённый текст)
    draw.text((x+4, y+4), text, font=font, fill=shadow_color)
    
    # Рисуем КОНТУР (обводку) — вокруг текста
    for dx in [-2, -1, 1, 2]:
        for dy in [-2, -1, 1, 2]:
            if dx or dy:
                draw.text((x+dx, y+dy), text, font=font, fill=outline_color)
    
    # Рисуем САМ ТЕКСТ
    draw.text((x, y), text, font=font, fill=main_color)
    
    output_path = "btc_price_output.jpg"
    
    # Сохраняем результат
    img.save(output_path)
    return output_path

# === Команды ===
# Команда /price
@tree.command(name="price", description="Show current BTC price", guild=discord.Object(id=GUILD_ID))
async def slash_price(interaction: discord.Interaction):
    allowed_channel_id = 1249289752998445109  # замените на ID нужного канала
    if interaction.channel.id != allowed_channel_id:
        await interaction.response.send_message(f"❌ This command is only available in the channel <#{allowed_channel_id}>", ephemeral=True)
        return
    if not os.path.exists(background_path):
        raise FileNotFoundError(f"Background image not found: {background_path}")
    if not os.path.exists(font_path):
        raise FileNotFoundError(f"Font not found: {font_path}")
    try:
        await interaction.response.defer()
        price = await get_btc_price()
        image_path = create_price_image(price)
        if not os.path.exists(image_path):
            await interaction.followup.send("❌ Failed to create image.")
            return
        await interaction.followup.send(
            content=f"Current price $BTC: ${price}",
            file=discord.File(image_path)
        )
        logging.info(f"Исользование команды /price Цена BTC: ${price}")
    except Exception as e:
        logging.error(f"Ошибка в /price: {e}")

# Команда /roll
@tree.command(name="roll", description="Random number 0-100", guild=discord.Object(id=GUILD_ID))
async def slash_roll(interaction: discord.Interaction):
    allowed_channel_id = 1375863859616677980  # замените на ID нужного канала
    if interaction.channel.id != allowed_channel_id:
        await interaction.response.send_message(f"❌ This command is only available in the channel <#{allowed_channel_id}>", ephemeral=True)
        return
    number = random.randint(0, 100)
    await interaction.response.send_message(f"🎲 **{number}**")
    
    # Логируем имя пользователя и его ID
    logging.info(f"/roll использовал: {interaction.user} (ID: {interaction.user.id}) — результат: {number}")

# === Твиты ===
async def fetch_and_send_tweets():
    global last_tweet_id
    try:
        if not TWITTER_USER_ID:
            logging.error("❌ TWITTER_USER_ID не установлен. Укажите его в .env")
            return
        # Получаем последние твиты, исключая ретвиты и реплаи
        tweets = twitter_client.get_users_tweets(
            id=TWITTER_USER_ID,
            max_results=5,
            tweet_fields=['created_at', 'referenced_tweets', 'attachments'],
            expansions=['attachments.media_keys'],
            media_fields=['url']
        )
        if tweets.data:
            channel = bot.get_guild(GUILD_ID).get_channel(TWITTER_CHANNEL_ID)
            media = {m["media_key"]: m for m in tweets.includes.get("media", [])} if tweets.includes else {}
            for tweet in reversed(tweets.data):
                if tweet.referenced_tweets:
                    continue
                
                if last_tweet_id and str(tweet.id) <= str(last_tweet_id):
                    continue  # Уже отправлено
                
                tweet_url = f"https://twitter.com/{TWITTER_USERNAME}/status/{tweet.id}"
                
                # Создаём кнопки
                view = View()
                view.add_item(Button(label="Open in Twitter", url=tweet_url, style=discord.ButtonStyle.link))
                view.add_item(Button(label="🔁 Retweet", url=f"https://twitter.com/intent/retweet?tweet_id={tweet.id}", style=discord.ButtonStyle.link))
                
                # Отправляем embed
                embed = discord.Embed(
                    title="📢 New tweet!",
                    description=tweet.text,
                    url=tweet_url,
                    color=discord.Color.blue()
                )
                embed.set_footer(text="Red_Planet_Dao")
                
                # Добавляем изображение, если есть
                if tweet.attachments and "media_keys" in tweet.attachments:
                    for key in tweet.attachments["media_keys"]:
                        if key in media and media[key].type == "photo":
                            embed.set_image(url=media[key].url)
                            break
                
                # Отправка сообщения с кнопкой
                msg = await channel.send(embed=embed, view=view)
                
                # Добавим реакции
                await msg.add_reaction("❤️")
                await msg.add_reaction("🔁")
                await msg.add_reaction("🔴")
                
                seen_tweet_ids.add(tweet.id)
                last_tweet_id = tweet.id
                save_last_tweet_id(last_tweet_id)
                logging.info(f"[TWITTER] Отправлен твит ID: {tweet.id}")
        else:
            logging.info("[TWITTER] Нет новых твитов.")
    except Exception as e:
        logging.error(f"[TWITTER] Ошибка: {e}")
    
    # Обработка ошибки 429
    except tweepy.TooManyRequests as e:
        logging.warning(f"[TWITTER] ❗ Превышен лимит запросов (429). Ждём 20 минут.")

# === Циклы задач ===
# Каждая операция идёт последовательно
async def btc_loop():
    await bot.wait_until_ready()
    while True:
        await update_btc_channel_name()  # обновление цены BTC
        await asyncio.sleep(600)         # обновление каждые 10 минут

async def twitter_loop():
    await bot.wait_until_ready()
    while True:
        await fetch_and_send_tweets()     # проверка твитов
        await asyncio.sleep(1200)         # обновление каждые 20 минут

@bot.event
async def on_ready():
    logging.info(f"✅ Бот вошёл как {bot.user}")
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    asyncio.create_task(btc_loop())
    asyncio.create_task(twitter_loop())

# === Запуск ===
def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    bot.run(DISCORD_TOKEN)
    
