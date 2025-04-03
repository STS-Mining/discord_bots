from discord.ext import commands, tasks
from dotenv import load_dotenv
import discord
import aiohttp
import time
import os

# Load env variables
load_dotenv()

# Get Discord bot token
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Define intents to enable message and member events
intents = discord.Intents.default()
intents.messages = True
intents.members = True

# Create a Discord bot instance
client = commands.Bot(command_prefix="!", intents=intents)

# Define a global variable to store the previous XeggeX value
last_notification_time = 0

def get_readable_hashrate(hashrate):
    factors = {0: 'H/s', 1: 'Kh/s', 2: 'Mh/s', 3: 'Gh/s', 4: 'Th/s', 5: 'Ph/s'}
    i = 0
    while hashrate >= 1000 and i < len(factors) - 1:
        hashrate /= 1000.0
        i += 1
    return '{:.2f} {}'.format(hashrate, factors[i])

# Function to set a voice channel to private (disconnect for everyone)
async def set_channel_private(category, channel):
    try:
        if isinstance(channel, discord.VoiceChannel) and channel.category == category:
            await channel.set_permissions(channel.guild.default_role, connect=False)
    except Exception as e:
        print(f"An error occurred while setting channel to private: {e}")

# Function to get or create a voice channel within a category
async def get_or_create_channel(category, channel_name):
    for existing_channel in category.voice_channels:
        existing_name = existing_channel.name.lower().replace(" ", "")
        target_name = channel_name.lower().replace(" ", "")
        if existing_name.startswith(target_name):
            return existing_channel

    channel = await category.create_voice_channel(channel_name)
    time.sleep(15)
    return channel

# Function to create or update a voice channel's name with specific formatting
async def create_or_update_channel(guild, category, channel_name, stat_value):
    try:
        channel = await get_or_create_channel(category, channel_name)

        if isinstance(stat_value, str) and stat_value == "N/A":
            formatted_value = stat_value
        else:
            if channel_name.lower() == "members:":
                formatted_value = "{:,.0f}".format(stat_value)
            elif channel_name.lower() == "supply:":
                formatted_value = "{:,.0f} YERB".format(stat_value)
            elif channel_name.lower() == "price: $":
                formatted_value = "{:.8f}".format(stat_value)
            elif channel_name.lower() == "hashrate:":
                formatted_value = get_readable_hashrate(float(stat_value)) if stat_value != "N/A" else stat_value
            elif channel_name.lower() == "market cap:":
                formatted_value = "{:,.2f}".format(round(stat_value))
            elif channel_name.lower() in "difficulty:":
                formatted_value = "{:,.8f}".format(stat_value)
            elif channel_name.lower() in "block:":
                formatted_value = "{:,.0f}".format(stat_value)
            elif channel_name.lower() == "24h volume:":
                formatted_value = "{:,.2f}".format(stat_value)
            else:
                formatted_value = stat_value

        await channel.edit(name=f"{channel_name} {formatted_value}")

    except Exception as e:
        print(f"An error occurred while updating channel name: {e}")


# Function to update all statistics channels within a guild
async def update_stats_channels(guild):
    global last_notification_time

    try:
        # Initialize variables to prevent errors if API calls fail
        difficulty = "N/A"
        hashrate = "N/A"
        block_count = "N/A"
        supply = "N/A"
        price = "N/A"
        volume_xeggex = "N/A"

        # Fetch server statistics from the APIs
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get("https://explorer.yerbas.org/api/getdifficulty") as response:
                    difficulty_data = await response.text()
                    difficulty = float(difficulty_data)
            except Exception:
                pass

            try:
                async with session.get("https://explorer.yerbas.org/api/getnetworkhashps") as response:
                    hashrate_data = await response.text()
                    hashrate = float(hashrate_data.strip())  # Convert to float
                    hashrate = await get_readable_hashrate(hashrate)  # Format it properly
            except Exception:
                pass

            try:
                async with session.get("https://explorer.yerbas.org/api/getblockcount") as response:
                    block_count = await response.text()
                    block_count = float(block_count)
            except Exception:
                pass

            try:
                async with session.get("https://explorer.yerbas.org/ext/getmoneysupply") as response:
                    supply_data = await response.text()
                    supply = float(supply_data)
            except Exception:
                pass

            try:
                async with session.get("https://api.xeggex.com/api/v2/market/getbysymbol/yerb_usdt") as response:
                    price_data = await response.json()
                    price = price_data["lastPrice"]
                    volume_yerb = price_data["volume"]
                    volume_xeggex = float(volume_yerb) * float(price)
            except Exception:
                pass

        # Ensure volume is formatted correctly
        volume = volume_xeggex if volume_xeggex != "N/A" else "N/A"

        # Fetch member count safely
        try:
            member_count = guild.member_count
        except Exception:
            member_count = "N/A"

        # Define the category name for statistics channels
        category_name = "Yerbas Server Stats"
        category = discord.utils.get(guild.categories, name=category_name)

        if not category:
            print(f"Creating category '{category_name}'")
            category = await guild.create_category(category_name)

        time.sleep(15)

        # Update or create individual statistics channels
        print(f"Members '{member_count}'")
        await create_or_update_channel(guild, category, "Members:", member_count)
        time.sleep(15)
        print(f"Difficulty '{difficulty}'")
        await create_or_update_channel(guild, category, "Difficulty:", difficulty)
        time.sleep(15)
        print(f"Hashrate '{hashrate}'")
        await create_or_update_channel(guild, category, "Hashrate:", hashrate)
        time.sleep(15)
        print(f"Block '{block_count}'")
        await create_or_update_channel(guild, category, "Block:", block_count)
        time.sleep(15)
        print(f"Supply '{supply}'")
        await create_or_update_channel(guild, category, "Supply:", supply)
        time.sleep(15)
        print(f"Price '{price}'")
        if price != "N/A":
            await create_or_update_channel(guild, category, "Price: $", float(price))
        else:
            await create_or_update_channel(guild, category, "Price: $", price)
        time.sleep(15)
        
        formatted_volume = "{:,.2f}".format(volume) if volume != "N/A" else "N/A"
        print(f"24h Volume '{formatted_volume}'")
        await create_or_update_channel(guild, category, "24h Volume: $", formatted_volume)
        time.sleep(15)

        if supply != "N/A" and price != "N/A":
            market_cap = round(supply * float(price))
            formatted_market_cap = "{:,.2f}".format(market_cap)
        else:
            formatted_market_cap = "N/A"
        print(f"Market Cap '{formatted_market_cap}'")
        await create_or_update_channel(guild, category, "Market Cap: $", formatted_market_cap)
        time.sleep(15)

        # Set all channels to private
        for channel in category.voice_channels:
            await set_channel_private(category, channel)

    except Exception as e:
        print(f"An error occurred while updating channels: {e}")


# Define a task to update statistics channels every 5 minutes
@tasks.loop(minutes=5)
async def update_stats_task():
    start_time = time.time()  # Start timer
    
    for guild in client.guilds:
        print(f"Updating stats for guild '{guild.name}'")
        await update_stats_channels(guild)

    end_time = time.time()  # End timer
    elapsed_time = end_time - start_time
    print(f"Update completed in {elapsed_time:.2f} seconds")

@client.event
async def on_ready():
    print("The bot is ready")
    update_stats_task.start()

# Run the bot with the provided token
client.run(TOKEN)
