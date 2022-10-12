import asyncio
import contextlib
import datetime
import json

import aiohttp
import discord
import pytz
from redbot.core import commands
from redbot.core.data_manager import bundled_data_path, cog_data_path

ReqHeaders = {
    "Authorization": "basic T64Mdy7m[",
    "Content-Type": "application/json; charset=utf-8",
    "credentials": "include",
    "Referer": "https://opentimetable.dcu.ie/",
    "Origin": "https://opentimetable.dcu.ie/",
}

COURSES = {
    "COMSCI1": [894237845802344478, 894239236352507976],
    "CASE2": [889594375598923857, 894239188931706972],
    "CASE3": [889591587213045810, 894239169407246428],
    "CASE4": [889594398613069874, 894239034304507914],
}

GUILD = 713522800081764392
# GUILD = 397040193720287243

# COURSES = {
#     "CASE4": [693451350775955518, 898944947938529320]
# }


class AutoTimetable(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.req_data = self.get_req_data()
        self.loop = asyncio.ensure_future(self.initialise())

    def get_req_data(self):
        with open(bundled_data_path(self) / "request.json") as f:
            return json.load(f)

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
        self.loop.cancel()

    async def initialise(self):
        await self.bot.wait_until_ready()
        dub = pytz.timezone("Europe/Dublin")
        with contextlib.suppress(RuntimeError):
            while True:
                try:
                    await self.post_timetables()
                except Exception as e:
                    print(e)
                now = datetime.datetime.now().astimezone(dub)
                tomorrow = (now + datetime.timedelta(days=1)).replace(hour=20, minute=0, second=0, microsecond=0)
                await asyncio.sleep((tomorrow - now).total_seconds())

    async def post_timetables(self, *, skip=False):
        try:
            dub = pytz.timezone("Europe/Dublin")
            if not skip:
                timedel = (datetime.datetime.now()  + datetime.timedelta(days=1)).astimezone(dub)
                today = timedel.date()
                if timedel.weekday() == 5:
                    timedel = (datetime.datetime.now()  + datetime.timedelta(days=3)).astimezone(dub)
                    today = timedel.date()
                elif timedel.weekday() == 6:
                    timedel = (datetime.datetime.now()  + datetime.timedelta(days=2)).astimezone(dub)
                    today = timedel.date()
            else:
                today = datetime.datetime.now().astimezone(dub).date()
            for course in COURSES:
                async with self.session.post(
                    f"https://opentimetable.dcu.ie/broker/api/CategoryTypes/241e4d36-60e0-49f8-b27e-99416745d98d/Categories/Filter?pageNumber=1&query={course}",
                    headers=ReqHeaders,
                ) as req:
                    if req.status != 200:
                        continue
                    data = (await req.json())["Results"][0]["Identity"]
                self.req_data["CategoryIdentities"][0] = data

                async with self.session.post(
                    f"https://opentimetable.dcu.ie/broker/api/categoryTypes/241e4d36-60e0-49f8-b27e-99416745d98d/categories/events/filter",
                    headers=ReqHeaders,
                    json=self.req_data,
                ) as req:
                    if req.status != 200:
                        continue
                    timetable = await req.json()
                embed = discord.Embed(title=f"Timetable for {course} for {today.strftime('%A')} {today.strftime('%d/%m/%Y')}")
                string = ""
                for event_obj in sorted(timetable[0]["CategoryEvents"], key=lambda x: datetime.datetime.fromisoformat(x["StartDateTime"])):
                    start = datetime.datetime.fromisoformat(event_obj["StartDateTime"]).astimezone(dub)
                    if start.date() != today:  # datetime.datetime.now().date():
                        # print(f"{start} not today")
                        continue
                    end = datetime.datetime.fromisoformat(event_obj["EndDateTime"]).astimezone(dub)
                    duration = end - start

                    string += f"**{event_obj['ExtraProperties'][0]['Value']}** | {start.strftime('%I:%M%p').lstrip('0')} - {end.strftime('%I:%M%p').lstrip('0')} - {duration.seconds // 3600}h \n{event_obj['Location']} - <t:{int(today.timestamp())}:R>\n\n"
                if string == "":
                    string = f"No classes found for {today.strftime('%A')}"
                embed.description = string
                guild = self.bot.get_guild(GUILD)
                channel = guild.get_channel(COURSES[course][0])
                msg = channel.get_partial_message(COURSES[course][1])
                await msg.edit(embed=embed)
        except Exception as e:
            print(e)
