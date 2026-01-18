#!/usr/bin/env python3
import ast
import asyncio
import logging
import os
from logging.handlers import RotatingFileHandler
from typing import cast

import discord
import requests
import unicodedata
from discord.ext import commands

import Config

def _parse_filters(raw: str):
    try:
        return ast.literal_eval(raw)
    except Exception:
        return []

intents = discord.Intents.default()
intents.message_content = True  # IMPORTANT

bot = commands.Bot(command_prefix="!", intents=intents)

_scan_task = None

@bot.event
async def on_ready():
    global _scan_task
    logging.info(f"[DISCORD] Connecté en tant que {bot.user}")

    if _scan_task is None:  # évite double lancement si reconnexion
        load_analyzed_item()
        _scan_task = asyncio.create_task(auto_scan_loop())

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purgeall(ctx):
    """
    !purgeall -> supprime tous les messages du salon (moins de 14 jours)
    """

    # supprime aussi la commande
    await ctx.message.delete()

    deleted = await ctx.channel.purge(limit=None)

    msg = await ctx.send(f"🧹 Salon nettoyé ({len(deleted)} messages supprimés).", delete_after=3)

@bot.command()
async def scanfull(ctx, *, arg: str):
    """
    !scanfull <search text> | [filters]
    """

    ALLOWED_CHANNEL = int(os.getenv("SCAN_COMMAND_CHANNEL_ID"))

    if ctx.channel.id != ALLOWED_CHANNEL:
        await ctx.send("❌ Cette commande est disponible uniquement dans #scan-manuel.")
        return

    if "|" in arg:
        search_text, raw_filters = arg.split("|", 1)
        search_text = search_text.strip()
        raw_filters = raw_filters.strip()
        title_filters = _parse_filters(raw_filters)
    else:
        search_text = arg.strip()
        title_filters = []

    guild = ctx.guild

    # supprime le message commande !scanfull
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass

    CATEGORY_ID = int(os.getenv("SCAN_CATEGORY_ID"))
    category = discord.utils.get(guild.categories, id=CATEGORY_ID)

    safe_name = search_text.replace(" ", "-").lower()[:90]
    temp_channel = await guild.create_text_channel(
        name=safe_name,
        category=category
    )

    progress_msg = await ctx.send(
        f"🔍 **Scan en cours...**\n"
        f"Recherche : `{search_text}`\n"
        f"Filtres : `{title_filters or 'Aucun'}`\n"
        f"Pages : en cours...\n"
        f"Cartes trouvées : 0"
    )

    params = {
        "page": "1",
        "per_page": "96",
        "search_text": search_text,
        "order": "newest_first",
        "max_page": "80",
        "title_filters": title_filters,
    }

    found_count_box = {"n": 0}

    params["_found_box"] = found_count_box

    async def progress_cb(done, total):
        await progress_msg.edit(
            content=
            f"🔍 **Scan en cours...**\n"
            f"Recherche : `{search_text}`\n"
            f"Filtres : `{title_filters or 'Aucun'}`\n"
            f"Page : {done} / {total}\n"
            f"Cartes trouvées : {found_count_box['n']}"
        )

    found_count = await scan_vinted(
        params,
        full_scan=True,
        send_channel_id=temp_channel.id,
        progress_cb=progress_cb
    )

    # -------- done --------
    await progress_msg.edit(
        content=
        f"✅ **Scan terminé !**\n"
        f"Recherche : `{search_text}`\n"
        f"Cartes trouvées : {found_count}\n"
        f"Résultats : {temp_channel.mention}"
    )

async def send_embed(embed, view, discord_channel_id: int):
    # bot.wait_until_ready() = équivalent propre
    await bot.wait_until_ready()

    channel = bot.get_channel(int(discord_channel_id))
    if channel is None:
        try:
            channel = await bot.fetch_channel(int(discord_channel_id))
        except Exception:
            logging.error("[DISCORD] Channel introuvable", exc_info=True)
            return

    await channel.send(embed=embed, view=view)

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
    except FileNotFoundError:
        logging.info("vinted_items.txt not found, starting fresh.")
    except Exception as e:
        logging.error("Error loading analyzed items", exc_info=True)

# Save a new analyzed item to prevent repeated alerts
def save_analyzed_item(hash):
    try:
        with open("vinted_items.txt", "a") as f:
            f.write(str(hash) + "\n")
    except Exception as e:
        logging.error("Error saving analyzed item", exc_info=True)

async def send_discord_message(username, item_title, item_price, item_url, item_image, discord_channel_id: int):
    embed = discord.Embed(
        title = "🆕 Nouvelle(s) carte(s) Vinted",
        description = f"**{item_title}**",
        color = 0x2ECC71,
        url = item_url
    )

    embed.set_image(url = item_image)

    embed.set_author(
        name = f"👤 {username}",
    )

    embed.add_field(name = "💰 Prix", value = item_price, inline = True)
    embed.add_field(name = "🔗 Annonce", value = f"[Ouvrir sur Vinted]({item_url})", inline = True)

    embed.set_footer(text = "Voggt Scanner • Vinted")

    view = discord.ui.View()
    view.add_item(
        discord.ui.Button(
            label = "📲 Ouvrir dans Vinted",
            style = cast(discord.ButtonStyle, discord.ButtonStyle.link),
            url = item_url
        )
    )

    try:
        await send_embed(embed, view, discord_channel_id)
    except Exception as e:
        logging.error("Error sending Discord embed", exc_info = True)

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

async def scan_vinted(params, *, full_scan=False, send_channel_id=None, progress_cb=None):

    session = requests.Session()
    session.post(Config.vinted_url, headers=headers, timeout=timeoutconnection)
    cookies = session.cookies.get_dict()

    api_params = {
        "page": "1",
        "per_page": params.get("per_page", "96"),
        "search_text": params.get("search_text", "*"),
        "catalog_ids": params.get("catalog_ids", ""),
        "brand_ids": params.get("brand_ids", ""),
        "order": params.get("order", "newest_first"),
    }

    # ---- première requête ----
    r = requests.get(
        f"{Config.vinted_url}/api/v2/catalog/items",
        params=api_params,
        cookies=cookies,
        headers=headers,
        timeout=timeoutconnection
    )
    data = r.json()

    pagination = data.get("pagination", {})
    total_pages = int(pagination.get("total_pages", 1))

    logging.info(f"[SCAN] pages {total_pages} -> 1 | {params.get('search_text')}")

    # ---- boucle pages ----
    found = 0
    if full_scan:
        pages = range(1, total_pages + 1)
    else:
        pages = range(1, min(total_pages, 1) + 1)

    for idx, page in enumerate(pages, start = 1):
        if progress_cb:
            await progress_cb(idx, len(pages))
        api_params["page"] = str(page)

        r = session.get(
            f"{Config.vinted_url}/api/v2/catalog/items",
            params=api_params,
            cookies=cookies,
            headers=headers,
            timeout=timeoutconnection
        )

        data = r.json()
        items = data.get("items", [])

        for item in items:
            item_id = str(item["id"])
            item_title = item["title"]

            title_filters = params.get("title_filters", [])
            if title_filters and not _title_matches_filters(item_title, title_filters):
                continue

            user = item.get("user") or {}
            username = user.get("login", "N/A")

            item_url = item["url"]
            item_price = f'{item["price"]["amount"]} {item["price"]["currency_code"]}'
            item_image = item["photo"]["full_size_url"]

            if item_id not in list_analyzed_items or full_scan:
                await send_discord_message(
                    username,
                    item_title,
                    item_price,
                    item_url,
                    item_image,
                    send_channel_id or params.get("discord_channel_id")
                )

                found += 1
                box = params.get("_found_box")
                if box is not None:
                    box["n"] = found

                if progress_cb and found % 5 == 0:
                    await progress_cb(idx, len(pages))

                if not full_scan:
                    list_analyzed_items.append(item_id)
                    save_analyzed_item(item_id)

        if progress_cb:
            await progress_cb(idx, len(pages))
        await asyncio.sleep(0.4)
    return found

async def scan_vinted_once():
    for params in Config.queries:
        await scan_vinted(params, full_scan=False)

async def auto_scan_loop():
    while True:
        try:
            await scan_vinted_once()
        except Exception:
            logging.error("auto_scan_loop crashed", exc_info=True)
        await asyncio.sleep(600)

if __name__ == "__main__":
    bot.run(Config.DISCORD_TOKEN)