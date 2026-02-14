import feedparser
import os
import re
import datetime
import time
import requests
from telegram import Bot
import asyncio

# --- Configuration ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID")
DISCORD_USER_TOKEN = os.environ.get("DISCORD_USER_TOKEN")
DISCORD_CHANNEL_ID = os.environ.get("DISCORD_CHANNEL_ID")

TARGET_SUBREDDITS = ["Tacticus_Codes", "WarhammerTacticus"]
KNOWN_CODES_FILE = "known_codes.txt"

# Regex: Uppercase alphanumeric, 4-20 chars, MUST contain at least one letter (no pure numbers)
CODE_PATTERN = re.compile(r'\b(?=[A-Z0-9]*[A-Z])[A-Z0-9]{4,20}\b')

# Words to ignore (Common false positives)
IGNORE_LIST = {
    "CODE", "CODES", "REDDIT", "TACTICUS", "WARHAMMER", "DISCORD", "LINK", "GAME", 
    "FREE", "REWARD", "ANDROID", "IPHONE", "MOBILE", "UPDATE", "PATCH",
    "NOTES", "HAVE", "BEEN", "THIS", "THAT", "WITH", "FROM", "POST",
    "THEY", "YOUR", "WILL", "JUST", "LIKE", "GOOD", "LUCK", "GUYS",
    "THANKS", "THANK", "YOU", "GUILD", "RAID", "ARENA", "MODE", "HELP",
    "NEED", "WANT", "LOOK", "FIND", "JOIN", "TEAM", "PLAY", "BEST",
    "META", "TIER", "LIST", "VIEW", "POLL", "VOTE", "MEME", "FLUFF",
    "NEWS", "INFO", "CHAT", "RULE", "MODS", "USER", "BOTS", "TEST",
    "HTTP", "HTTPS", "COM", "WWW", "REDDIT", "COMMENTS", "PERMALINK",
    "REFERRAL", "REFERRALS", "VIDEO", "YOUTUBE", "SHARDS", "GOLD", "BLACKSTONE",
    "UPDATED", "WORKING", "ITEMS", "REQUISITION", "ORDERS", "PLAYERS", "NEWEST", "TOP",
    "ALL", "AND", "FOR", "OLD", "NEW"
}

def load_known_codes():
    if not os.path.exists(KNOWN_CODES_FILE):
        return set()
    with open(KNOWN_CODES_FILE, "r") as f:
        return set(line.strip() for line in f)

def save_new_code(code):
    with open(KNOWN_CODES_FILE, "a") as f:
        f.write(f"{code}\n")

async def send_telegram_message(code, source_url):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        print(f"Skipping Telegram send (no creds): {code}")
        return

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    # MODIFIED: Showing source link again, but disabling preview
    message = f"🆕 **New Tacticus Code Found!**\n\n`{code}`\n\n[Source]({source_url})"
    try:
        await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=message, parse_mode='Markdown', disable_web_page_preview=True)
        print(f"Sent code to Telegram: {code}")
    except Exception as e:
        print(f"Failed to send message: {e}")

def check_discord(known_codes):
    """
    Polls the Discord Channel API using a User Token.
    Returns: None (updates known_codes in place)
    """
    if not DISCORD_USER_TOKEN or not DISCORD_CHANNEL_ID:
        print("Skipping Discord check (no secrets provided).")
        return

    url = f"https://discord.com/api/v9/channels/{DISCORD_CHANNEL_ID}/messages?limit=10"
    headers = {"Authorization": DISCORD_USER_TOKEN}

    print(f"Checking Discord Channel {DISCORD_CHANNEL_ID}...")
    try:
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            print(f"Discord Error {r.status_code}: {r.text}")
            return
        
        # Messages from newest to oldest
        messages = r.json()
        
        for msg in messages:
            content = msg.get('content', '')
            
            
            potential_codes = CODE_PATTERN.findall(content)
            
            for code in potential_codes:
                if code in IGNORE_LIST:
                    continue
                
                if code not in known_codes:
                    print(f"New Code Found via Discord: {code}")
                    # Construct a jump link
                    msg_link = f"https://discord.com/channels/@me/{DISCORD_CHANNEL_ID}/{msg['id']}"
                    
                    asyncio.run(send_telegram_message(code, msg_link))
                    known_codes.add(code)
                    save_new_code(code)

    except Exception as e:
        print(f"Error checking Discord: {e}")

def main():
    if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID]):
        print("Warning: Missing Telegram environment variables. Bot will only print to console.")

    known_codes = load_known_codes()
    print(f"Loaded {len(known_codes)} known codes.")

    # Calculate cutoff time (3 days ago)
    # RSS entries usually have 'published_parsed' struct_time
    cutoff_time = datetime.datetime.utcnow() - datetime.timedelta(days=3)

    # 1. Check Discord
    check_discord(known_codes)

    # 2. Check Reddit
    for sub_name in TARGET_SUBREDDITS:
        rss_url = f"https://www.reddit.com/r/{sub_name}/new/.rss"
        print(f"Checking {rss_url}...")
        
        try:
            feed = feedparser.parse(rss_url)
            
            for entry in feed.entries:
                # Check date
                if hasattr(entry, 'published_parsed'):
                    published_dt = datetime.datetime.fromtimestamp(time.mktime(entry.published_parsed))
                    if published_dt < cutoff_time:
                        continue # Too old
                
                # Combine title and content/summary
                # Reddit RSS puts the post content in 'content' or 'summary' with HTML
                content_text = entry.title
                if hasattr(entry, 'summary'):
                     content_text += " " + entry.summary
                
                # Simple HTML tag strip (rough) because regex runs on text
                content_text = re.sub('<[^<]+?>', ' ', content_text)

                potential_codes = CODE_PATTERN.findall(content_text)

                for code in potential_codes:
                    if code in IGNORE_LIST:
                        continue
                    
                    if code not in known_codes:
                        # Found a new code!
                        print(f"New Code Found: {code} from {entry.link}")
                        
                        # Send to Telegram
                        asyncio.run(send_telegram_message(code, entry.link))
                        
                        # Add to known codes
                        known_codes.add(code)
                        save_new_code(code)

        except Exception as e:
            print(f"Error checking {sub_name}: {e}")

if __name__ == "__main__":
    main()
