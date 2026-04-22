import os
import json
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# JSON file path — single source of truth for all category-channel mappings
CATEGORIES_FILE = "job_categories.json"


# Load all categories from JSON file
def load_categories() -> dict:
    if not os.path.exists(CATEGORIES_FILE):
        return {}
    with open(CATEGORIES_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️  Warning: {CATEGORIES_FILE} is corrupted. Returning empty categories.")
            return {}


# Save updated categories back to JSON file
def save_categories(data: dict):
    with open(CATEGORIES_FILE, "w") as f:
        json.dump(data, f, indent=4)


# Class Handles all Discord commands for dynamic channel management.
# Loaded as an extension in main.py via bot.load_extension()
class ChannelsHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # !add channel <name>
    @commands.command(name="add")
    async def add_channel(self, ctx, subcommand: str, *, category_name: str):
        # Only handle "channel" subcommand
        if subcommand.lower() != "channel":
            await ctx.send(
                f"⚠️  Unknown subcommand `{subcommand}`. Usage: `!add channel <name>`"
            )
            return

        # Normalize category name for consistent storage and lookup
        category_key = category_name.strip().title()

        # Channel names cannot have spaces — Discord rejects them
        channel_slug = category_key.replace(" ", "-").lower()

        # Check if this category already exists
        data = load_categories()
        if category_key in data:
            await ctx.send(
                f"⚠️  Category **{category_key}** already exists → <#{data[category_key]}>"
            )
            return

        # Create the Discord text channel
        try:
            new_channel = await ctx.guild.create_text_channel(f"{channel_slug}-jobs")
        except discord.Forbidden:
            await ctx.send(
                "❌ Error: Bot does not have **Manage Channels** permission. "
                "Grant this permission in Server Settings and try again."
            )
            return
        except discord.HTTPException as e:
            await ctx.send(f"❌ Discord error while creating channel: {e}")
            return
        except Exception as e:
            await ctx.send(f"❌ Unexpected error: {e}")
            return

        # Save new entry to JSON after successful channel creation
        data[category_key] = str(new_channel.id)
        save_categories(data)

        print(f"✅  Category '{category_key}' added → channel '{channel_slug}-jobs' (ID: {new_channel.id})")
        await ctx.send(
            f"✅ Category **{category_key}** added and channel <#{new_channel.id}> created!"
        )

    # !delete channel <name>
    @commands.command(name="delete")
    async def delete_channel(self, ctx, subcommand: str, *, category_name: str):
        # 1. Subcommand check
        if subcommand.lower() != "channel":
            await ctx.send(f"⚠️ Unknown subcommand `{subcommand}`. Usage: `!delete channel <name>`")
            return

        category_key = category_name.strip().title()
        data = load_categories()

        # 2. Check if category exists in JSON
        if category_key not in data:
            await ctx.send(f"❌ Error: Category **{category_key}** record not found, available categories: {', '.join(data.keys())}")
            return

        stored_channel_id = int(data[category_key])
        current_channel_id = ctx.channel.id

        # 3. Security Condition: Command must be run in the channel that is linked to the category being deleted
        if current_channel_id != stored_channel_id:
            await ctx.send(
                f"❌ Security Block: You can only delete the category from its own channel. Please run this command in <#{stored_channel_id}>."
            )
            return

        channel_to_delete = self.bot.get_channel(stored_channel_id)

        # 4. Deletion process
        try:
            # If channel is already deleted (e.g., manually by admin), we should still remove the JSON record without error
            if channel_to_delete:
                await ctx.send(f"🗑️ Deleting channel for **{category_key}** in 3 seconds...")
                await asyncio.sleep(3) # Thora wait taake message dikh jaye
                await channel_to_delete.delete()
            else:
                print(f"⚠️ Discord channel already missing for {category_key}, just cleaning JSON.")

            # 5. JSON Update : Remove the category record from JSON file
            del data[category_key]
            save_categories(data)
            
            print(f"✅ Category '{category_key}' and its record removed successfully.")
            # Note: ctx.send don't work after channel deletion, so we won't send a confirmation message in Discord.

        except discord.Forbidden:
            await ctx.send("❌ Error: Bot does not have **Manage Channels** permission.")
        except discord.HTTPException as e:
            await ctx.send(f"❌ Discord error: {e}")
        except Exception as e:
            await ctx.send(f"❌ Unexpected error: {e}")

    # !list channels
    @commands.command(name="list")
    async def list_channels(self, ctx, subcommand: str = "channels"):
        if subcommand.lower() != "channels":
            await ctx.send(
                f"⚠️  Unknown subcommand `{subcommand}`. Usage: `!list channels`"
            )
            return

        data = load_categories()
        if not data:
            await ctx.send(
                "⚠️  No categories found. Use `!add channel <name>` to add one."
            )
            return

        lines = [f"• **{name}** → <#{cid}>" for name, cid in data.items()]
        embed = discord.Embed(
            title="📋  Active Job Categories",
            description="\n".join(lines),
            colour=0x1DBF73,
        )
        await ctx.send(embed=embed)

    # Error handler — user gets clear feedback instead of silence
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                f"⚠️  Missing argument: `{error.param.name}`\n"
                f"Usage: `!add channel <name>` or `!delete channel <name>`"
            )
        elif isinstance(error, commands.CommandNotFound):
            pass  # Silently ignore unknown commands — no spam
        elif isinstance(error, commands.BadArgument):
            await ctx.send("⚠️  Invalid argument. Please check command usage.")
        else:
            await ctx.send(f"❌ An error occurred: {error}")
            print(f"❌  Command error in '{ctx.command}': {error}")


# Required by discord.py for load_extension() in main.py
async def setup(bot):
    await bot.add_cog(ChannelsHandler(bot))


"""
# TESTING BLOCK
# Run standalone to verify load/save functions work correctly

# Test load
cats = load_categories()
print("Current categories:", cats)

# Test save
# cats["TestCategory"] = "123456789"
# save_categories(cats)
# print("Saved:", load_categories())
"""