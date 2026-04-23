import time
import asyncio
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from job_fetcher import process_and_store_jobs, get_new_job_ids
from discord_notifier import discord_post
from channels_handling import load_categories
from logger_config import log

load_dotenv()

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)


# Main function to process each category: Fetch jobs, identify new ones, and post to Discord
async def process_category(category_name, channel_id):
    print(f"\n--- Processing Category: {category_name} ---")
    try:
        # 1. Fetch latest jobs and store in database (Scraping part)
        process_and_store_jobs(f"{category_name}", 1)

        # 2. Retrieve Job IDs that are new and not yet posted to Discord
        new_job_ids = get_new_job_ids(category=category_name)

        if not new_job_ids:
            print(f"✅  Info: No new {category_name} jobs found at this time.")
            return

        log.info(f"✅  Success: Found {len(new_job_ids)} new jobs for {category_name}. Sending to Discord...")

        # 3. Post each new job to its respective Discord channel
        for job_id in new_job_ids:
            try:
                await discord_post(channel_id=int(channel_id), job_id=job_id)
            except Exception as e:
                log.error(f"❌  Error: Failed to post job {job_id} for {category_name}: {e}")

        log.info(f"✅  Posted latest {len(new_job_ids)} jobs for {category_name}.")

    except Exception as e:
        log.error(f"❌  Exception in {category_name} process: {e}")


# Background loop — runs all categories concurrently every 10 seconds
async def job_monitor():
    await bot.wait_until_ready()
    print("Bot Started: Monitoring Upwork for Multiple Categories...")

    while not bot.is_closed():
        start_time = time.time()

        # Load categories fresh every cycle — picks up any !add / !delete changes
        JOB_CATEGORIES = load_categories()

        try:
            if not JOB_CATEGORIES:
                print("⚠️  No categories found in job_categories.json. Skipping this cycle.")
            else:
                # Run all category tasks concurrently
                tasks = [
                    process_category(category, cid)
                    for category, cid in JOB_CATEGORIES.items()
                ]
                await asyncio.gather(*tasks)

        except Exception as e:
            log.error(f"❌  System Error: {e}")

        log.info(f"--- Batch Completed in {round(time.time() - start_time, 2)}s. ---\n")
        print("Waiting 10 Seconds for the next cycle...\n")
        await asyncio.sleep(10)


# Bot ready event
@bot.event
async def on_ready():
    log.info(f"\n\n✅  Bot connected as {bot.user} \n")


# Load extensions and start bot
async def main():
    async with bot:
        # Load channels handler — registers !add, !delete, !list commands
        await bot.load_extension("channels_handling")

        # Start job monitor as background task
        asyncio.create_task(job_monitor())

        token = os.getenv("DISCORD_TOKEN")
        if not token:
            log.error("❌  Error: DISCORD_TOKEN missing from .env file.")
            return

        await bot.start(token)


"""
# TESTING: Run a single category once without the loop
async def test():
    await process_category("Python", 1496465492372750498)

asyncio.run(test())
"""


if __name__ == "__main__":
    asyncio.run(main())