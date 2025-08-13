# main.py
import os
from datetime import datetime

import aiohttp
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

import database
from keep_alive import keep_alive

# --- SETUP ---
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CLIST_API_KEY = os.getenv("CLIST_API_KEY")

# Define intents
intents = discord.Intents.default()
intents.message_content = True

# Create bot instance
bot = commands.Bot(command_prefix="/", intents=intents)

# --- DATABASE SETUP ---
database.initialize_db()

# --- UTILITY FUNCTIONS ---


def format_time(time_str):
    """Converts ISO 8601 time string to a Discord timestamp."""
    dt_object = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
    unix_timestamp = int(dt_object.timestamp())
    return f"<t:{unix_timestamp}:R>"


# --- API INTERACTION ---


async def fetch_contests():
    """Fetches contest data from the CLIST API."""
    # 1: Codeforces, 2: CodeChef, 93: AtCoder, 102: LeetCode
    resource_ids = "1,2,93,102"
    url = f"https://clist.by/api/v4/contest/?upcoming=true&resource_id__in={
        resource_ids
    }&order_by=start"
    headers = {"Authorization": f"ApiKey {CLIST_API_KEY}"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("objects", [])
            else:
                print(f"Failed to fetch from CLIST API. Status: {response.status}")
                return None


# --- UI COMPONENTS (VIEWS) ---


class ContestView(discord.ui.View):
    def __init__(self, contests, *, timeout=180):
        super().__init__(timeout=timeout)
        self.contests_data = {
            str(i): contest for i, contest in enumerate(contests[:25])
        }
        self.selected_contest_key = None
        self.add_item(self.create_dropdown())

    def create_dropdown(self):
        options = [
            discord.SelectOption(
                label=f"{contest['resource']}: {contest['event']}",
                value=key,
                description=f"Starts {format_time(contest['start'])}",
            )
            for key, contest in self.contests_data.items()
        ]
        select = discord.ui.Select(
            placeholder="Select a contest to see details...", options=options
        )
        select.callback = self.dropdown_callback
        return select

    async def dropdown_callback(self, interaction: discord.Interaction):
        self.selected_contest_key = interaction.data["values"][0]
        contest = self.contests_data[self.selected_contest_key]

        embed = discord.Embed(
            title=f"{contest['resource']}: {contest['event']}",
            url=contest["href"],
            description=f"This contest is scheduled to start {
                format_time(contest['start'])
            }.",
            color=discord.Color.green(),
        )
        embed.add_field(
            name="Duration", value=f"{int(contest['duration']) // 3600} hours"
        )
        embed.add_field(name="Platform", value=contest["resource"])
        embed.set_footer(
            text="Click the button below to be reminded 15 minutes before it starts."
        )

        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label="Remind Me", style=discord.ButtonStyle.success)
    async def remind_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not self.selected_contest_key:
            await interaction.response.send_message(
                "Please select a contest from the dropdown first!", ephemeral=True
            )
            return

        contest = self.contests_data[self.selected_contest_key]
        was_added = database.add_reminder(
            interaction.user.id, contest["event"], contest["href"], contest["start"], 15
        )

        if was_added:
            await interaction.response.send_message(
                f"✅ Okay! I will DM you 15 mins before '{contest['event']}' begins.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "You are already subscribed to a reminder for this contest.",
                ephemeral=True,
            )


# --- BOT EVENTS AND TASKS ---


@bot.event
async def on_ready():
    """Event that fires when the bot is online and ready."""
    print(f"{bot.user} has connected to Discord!")
    check_reminders.start()
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)


@tasks.loop(minutes=1)
async def check_reminders():
    """Checks for due reminders every minute and sends them."""
    due_reminders = database.get_due_reminders()
    for rem_id, user_id, contest_name, contest_url in due_reminders:
        try:
            user = await bot.fetch_user(user_id)
            if user:
                await user.send(
                    f"⏰ **Reminder!** The contest **'{
                        contest_name
                    }'** is starting in about 15 minutes!\nGet ready here: {
                        contest_url
                    }"
                )
            database.delete_reminder(rem_id)
        except discord.errors.NotFound:
            print(f"Could not find user {user_id}. Deleting reminder.")
            database.delete_reminder(rem_id)
        except Exception as e:
            print(f"An error occurred while sending a reminder: {e}")


# --- SLASH COMMANDS ---


@bot.tree.command(name="ping", description="Check the bot's latency.")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"Pong! Latency: {round(bot.latency * 1000)}ms"
    )


@bot.tree.command(name="upcoming", description="Shows upcoming coding contests.")
async def upcoming(interaction: discord.Interaction):
    await interaction.response.defer()
    contests_list = await fetch_contests()

    if contests_list is None:
        await interaction.followup.send(
            "Sorry, I couldn't fetch contest data. The API might be down."
        )
        return
    if not contests_list:
        await interaction.followup.send(
            "No upcoming contests found on LeetCode, CodeForces, CodeChef, or AtCoder."
        )
        return

    embed = discord.Embed(
        title="Upcoming Contests",
        description="Select a contest from the dropdown menu to see details or set a reminder.",
        color=discord.Color.blue(),
    )
    view = ContestView(contests_list)
    await interaction.followup.send(embed=embed, view=view)


# --- RUN THE BOT ---
keep_alive()
bot.run(TOKEN)
