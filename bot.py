import praw
import os
import re
import datetime
from telegram import Bot
import asyncio

# --- Configuration ---
REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = "TacticusCodeBot/1.0"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID")

TARGET_SUBREDDITS = ["Tacticus_Codes", "WarhammerTacticus"]
KNOWN_CODES_FILE = "known_codes.txt"

# Regex for potential codes: Uppercase alphanumeric, 4-20 chars
CODE_PATTERN = re.compile(r'\b[A-Z0-9]{4,20}\b')

# Words to ignore (Common false positives)
IGNORE_LIST = {
    "CODE", "REDDIT", "TACTICUS", "WARHAMMER", "DISCORD", "LINK", "GAME", 
    "FREE", "REWARD", "ANDROID", "IPHONE", "MOBILE", "UPDATE", "PATCH",
    "NOTES", "HAVE", "BEEN", "THIS", "THAT", "WITH", "FROM", "POST",
    "THEY", "YOUR", "WILL", "JUST", "LIKE", "GOOD", "LUCK", "GUYS",
    "THANKS", "THANK", "YOU", "GUILD", "RAID", "ARENA", "MODE", "HELP",
    "NEED", "WANT", "LOOK", "FIND", "JOIN", "TEAM", "PLAY", "BEST",
    "META", "TIER", "LIST", "VIEW", "POLL", "VOTE", "MEME", "FLUFF",
    "NEWS", "INFO", "CHAT", "RULE", "MODS", "USER", "BOTS", "TEST"
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
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    message = f"🆕 **New Tacticus Code Found!**\n\n`{code}`\n\n[Source]({source_url})"
    try:
        await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=message, parse_mode='Markdown')
        print(f"Sent code to Telegram: {code}")
    except Exception as e:
        print(f"Failed to send message: {e}")

def main():
    if not all([REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID]):
        print("Error: Missing environment variables.")
        return

    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT
    )

    known_codes = load_known_codes()
    print(f"Loaded {len(known_codes)} known codes.")

    # Calculate cutoff time (3 days ago)
    cutoff_time = datetime.datetime.utcnow() - datetime.timedelta(days=3)
    cutoff_timestamp = cutoff_time.timestamp()

    for sub_name in TARGET_SUBREDDITS:
        print(f"Checking r/{sub_name}...")
        try:
            subreddit = reddit.subreddit(sub_name)
            # Check 'new' posts
            for post in subreddit.new(limit=20):
                if post.created_utc < cutoff_timestamp:
                    break  # Too old

                text_to_search = f"{post.title} {post.selftext}"
                potential_codes = CODE_PATTERN.findall(text_to_search)

                for code in potential_codes:
                    if code in IGNORE_LIST:
                        continue
                    
                    # Basic heuristic: Codes often have numbers or are distinct words
                    # Tacticus codes are usually ALL CAPS.
                    if code not in known_codes:
                        # Found a new code!
                        print(f"New Code Found: {code}")
                        
                        # Send to Telegram
                        asyncio.run(send_telegram_message(code, post.url))
                        
                        # Add to known codes
                        known_codes.add(code)
                        save_new_code(code)

        except Exception as e:
            print(f"Error checking {sub_name}: {e}")

if __name__ == "__main__":
    main()
