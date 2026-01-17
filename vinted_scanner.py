#!/usr/bin/env python3
import asyncio
import json
import logging
import sys
from logging.handlers import RotatingFileHandler

import discord
import requests
import unicodedata

import Config

DISCORD_TOKEN = Config.DISCORD_TOKEN

intents = discord.Intents.default()
client = discord.Client(intents=intents)

_discord_ready = asyncio.Event()

@client.event
async def on_ready():
    logging.info(f"[DISCORD] Connecté en tant que {client.user}")
    _discord_ready.set()

async def start_discord():
    try:
        await client.start(DISCORD_TOKEN)
    except Exception as e:
        logging.error(f"[DISCORD] Impossible de démarrer: {e}", exc_info=True)
        # on libère l'attente pour éviter un deadlock
        _discord_ready.set()

async def send_message(message: str, discord_channel_id: int):
    # attend au max 20s que discord soit prêt (ou qu'il ait échoué)
    await asyncio.wait_for(_discord_ready.wait(), timeout=20)

    # si le bot n'est pas connecté, on évite de planter
    if not client.is_ready():
        logging.error("[DISCORD] Bot non prêt / non connecté, message non envoyé.")
        return

    channel = client.get_channel(discord_channel_id)
    if channel is None:
        try:
            channel = await client.fetch_channel(discord_channel_id)
        except Exception as e:
            logging.error(f"[DISCORD] Channel introuvable: {e}", exc_info=True)
            return

    await channel.send(message)

# Configure a rotating file handler to manage log files
handler = RotatingFileHandler("vinted_scanner.log", maxBytes=5000000, backupCount=5)

logging.basicConfig(handlers=[handler], 
                    format="%(asctime)s - %(filename)s - %(funcName)10s():%(lineno)s - %(levelname)s - %(message)s", 
                    level=logging.INFO)

# Timeout configuration for the requests
timeoutconnection = 30

# List to keep track of already analyzed items
list_analyzed_items = []

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.8,en-US;q=0.5,en;q=0.3",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
    "Sec-GPC": "1",
    "Priority": "u=0, i",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
}

# Load previously analyzed item hashes to avoid duplicates
def load_analyzed_item():
    try:
        with open("vinted_items.txt", "r", errors="ignore") as f:
            for line in f:
                if line:
                    list_analyzed_items.append(line.rstrip())
    except IOError as e:
        logging.error(e, exc_info=True)
        sys.exit()

# Save a new analyzed item to prevent repeated alerts
def save_analyzed_item(hash):
    try:
        with open("vinted_items.txt", "a") as f:
            f.write(str(hash) + "\n")
    except IOError as e:
        logging.error(e, exc_info=True)
        sys.exit()

async def send_discord_message(item_title, item_price, item_url, item_image, discord_channel_id: int):
    message = (
        "🆕 **Nouvel article Vinted trouvé !**\n\n"
        f"👕 **Produit :** {item_title}\n"
        f"🏷️ **Prix :** {item_price}\n"
        f"🔗 **Lien :** {item_url}\n"
        f"🖼️ **Image :** {item_image}\n"
    )
    try:
        await send_message(message, discord_channel_id)
    except requests.exceptions.RequestException as e:
        logging.error(f"Error sending Telegram message: {e}")

def _norm(s: str) -> str:
    # lower + enlève les accents (dončić -> doncic)
    s = s.lower()
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def _title_matches_filters(title: str, filters) -> bool:
    """
    filters = ["luka", ["doncic","dončić"], ["rc","rookie"]]
    => chaque élément du top-level doit matcher:
       - str : doit être contenu
       - list : au moins un élément contenu
    """
    t = _norm(title)

    for f in filters:
        if isinstance(f, str):
            if _norm(f) not in t:
                return False
        elif isinstance(f, (list, tuple, set)):
            if not any(_norm(opt) in t for opt in f):
                return False
        else:
            # type inattendu => on considère que ça ne matche pas
            return False

    return True

async def scan_vinted_once():
    # Load the list of previously analyzed items
    load_analyzed_item()

    # Initialize session and obtain session cookies from Vinted
    session = requests.Session()
    session.post(Config.vinted_url, headers=headers, timeout=timeoutconnection)
    cookies = session.cookies.get_dict()
    
    # Loop through each search query defined in Config.py
    for params in Config.queries:
        # Request items from the Vinted API based on the search parameters
        response = requests.get(f"{Config.vinted_url}/api/v2/catalog/items", params=params, cookies=cookies, headers=headers)

        data = response.json()

        if data:
            # Process each item returned in the response
            for item in data["items"]:
                item_id = str(item["id"])
                item_title = item["title"]
                title_filters = params.get("title_filters", [])
                if title_filters and not _title_matches_filters(item_title, title_filters):
                    continue
                item_url = item["url"]
                item_price = f'{item["price"]["amount"]} {item["price"]["currency_code"]}'
                item_image = item["photo"]["full_size_url"]

                # Check if the item has already been analyzed to prevent duplicates
                if item_id not in list_analyzed_items:

                    await send_discord_message(item_title, item_price, item_url, item_image, params.get("discord_channel_id"))

                    # Mark item as analyzed and save it
                    list_analyzed_items.append(item_id)
                    save_analyzed_item(item_id)

async def main():
    discord_task = asyncio.create_task(start_discord())
    try:
        while True:
            await scan_vinted_once()
            await asyncio.sleep(600)
    finally:
        if client.is_ready() or client.is_closed() is False:
            await client.close()
        if not discord_task.done():
            discord_task.cancel()
            try:
                await discord_task
            except asyncio.CancelledError:
                pass

if __name__ == "__main__":
    asyncio.run(main())