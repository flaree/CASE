import asyncio

from pytz.exceptions import Error
import aiohttp
import json
import random
import secrets
from email.message import EmailMessage

import aiosmtplib
import discord
from redbot.core import Config, commands
from redbot.core.data_manager import bundled_data_path, cog_data_path
from redbot.core.utils.chat_formatting import pagify
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu
from redbot.core.utils.predicates import MessagePredicate


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i : i + n]


class Verify(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.config = Config.get_conf(self, identifier=95932766180343808, force_registration=True)
        self.config.register_global(
            username=None, password=None, verified_emails=[], welcome_messages=[]
        )
        self.config.register_user(code=None, verified=False, email=None, verified_by=None)
        self._init_task = self.bot.loop.create_task(self.initialize())

    async def initialize(self):
        """This will load all the bundled data into respective variables."""
        await self.bot.wait_until_red_ready()
        guild = self.bot.get_guild(713522800081764392)
        self.roles = {
            "case4": guild.get_role(713541403904442438),
            "case3": guild.get_role(713539660936118282),
            "case2": guild.get_role(713538655817564250),
            "ca": guild.get_role(713541535085494312),
            "case": guild.get_role(713538335984975943),
            "alumni": guild.get_role(713538175456247828),
        }
        tokens = await self.bot.get_shared_api_tokens("CASE")
        self.ReqHeaders = {
            "x-api-key": tokens.get("SOC_API_TOKEN")
        }

    async def get_course_year(self, email):
        """Fetch a user's course year via the SoC API"""
        async with self.session.get(
            f"https://ws.computing.dcu.ie/api/v1/course/{email}",
            headers=self.ReqHeaders,
        ) as req:
            if req.status != 200:
                return
            try:
                resp = (await req.json())
            except Exception as e:
                return False
            return resp

    def cog_unload(self):
        if self._init_task:
            self._init_task.cancel()
        self.bot.loop.create_task(self.session.close())
        self.loop.cancel()

    @commands.group()
    async def verify(self, ctx):
        """Verification process"""
        pass

    @commands.group()
    async def unverify(self, ctx):
        """Unverification process : )"""
        pass

    @unverify.command("me")
    async def unverify(self, ctx):
        """Unverify yourself"""
        user = ctx.message.author
        data = await self.config.user(user).all()
        if not data["verified"]:
            return await ctx.send("You are already not verified.")
        async with self.config.verified_emails() as emails:
            if data["email"] in emails:
                emails.remove(data["email"])
        await self.config.user(user).code.set(None)
        await self.config.user(user).verified.set(False)
        await self.config.user(user).email.set(None)
        await ctx.send("You have been un-verified. To re-verify DM me with `.verify email your_dcu_email_here` or contact an Admin.")

    @unverify.command("user")
    @commands.admin()
    async def unverify(self, ctx, *, user: discord.User):
        """Unverify someone"""
        data = await self.config.user(user).all()
        if not data["verified"]:
            return await ctx.send("This user isn't verified.")
        async with self.config.verified_emails() as emails:
            if data["email"] in emails:
                emails.remove(data["email"])
        await self.config.user(user).code.set(None)
        await self.config.user(user).verified.set(False)
        await self.config.user(user).email.set(None)
        await ctx.send("User has been un-verified.")

    @verify.command(name="email")
    @commands.dm_only()
    async def verify_email(self, ctx, email: str):
        """Verify your DCU email"""
        if email.lower().endswith("@dcu.ie"):
            await (self.bot.get_channel(713522800081764395)).send(
                f"{ctx.author} with the email {email} has tried to verify and can potentionally be a staff member."
            )
            return await ctx.send(
                "An error occured trying to verify your account. This error has been raised to the mod team."
            )
        if not email.lower().endswith("@mail.dcu.ie"):
            return await ctx.send("This doesn't seem to be a valid DCU email.")
        if await self.config.user(ctx.author).verified():
            await ctx.send("You have already been verified.")
            await (self.bot.get_channel(713522800081764395)).send(
                f"{ctx.author} with the email {email} has tried to verify with an email that has already been verified."
            )
            return
        emails = await self.config.verified_emails()
        if email in emails:
            await ctx.send("This email has already been verified.")
            return
        code = secrets.token_hex(3)
        await self.config.user(ctx.author).code.set(code)
        await self.config.user(ctx.author).email.set(email)
        await self.send_email(email, code)
        await ctx.send(
            f"You will recieve an email shortly. Once it arrived you may complete your verification process by typing:\n{ctx.clean_prefix}verify code <code from email>"
        )

    @verify.command(name="code")
    @commands.dm_only()
    async def verify_code(self, ctx, code):
        """Verify the code from your email"""
        usercode = await self.config.user(ctx.author).code()
        verified = await self.config.user(ctx.author).verified()
        if verified:
            await ctx.send("You are already verified.")
            return
        if usercode is None:
            await ctx.send(
                "You haven't started the verification process yet. Get started by invoking the .verify email command."
            )
            return
        if code == usercode:
            roles = []
            verified = await self.config.user(ctx.author).verified.set(True)
            await self.config.user(ctx.author).verified_by.set("System")
            email = await self.config.user(ctx.author).email()
            async with self.config.verified_emails() as emails:
                emails.append(email)
            guild = self.bot.get_guild(713522800081764392)
            role = guild.get_role(713538570824187968)
            user = guild.get_member(ctx.author.id)
            mod, general = self.bot.get_channel(713522800081764395), self.bot.get_channel(
                713524886840279042
            )
            greeting_msgs = await self.config.welcome_messages()

            # Set user nickname to real name if not already there

            user_email = await self.config.user(ctx.author).email()
            first_name = user_email.split(".")[0]
            name_len = 32 - len(f" ({first_name})")
            name = user.display_name[:name_len] + f" ({first_name.title()})"

            if first_name.lower() not in user.display_name.lower():
                await user.edit(nick=name)
            roles.append(role)

            # Check a the SoC API for course
            user_year = await self.get_course_year(email.lower())

            rolemsg = ""
            
            if type(user_year) != dict:
                rolemsg = "We were unable to determine your year of study. Please contact an admin to have a year role assigned to you."
            else:
                if user_year['course'] == "COMSCI1":
                    rolemsg = "We've automatically determined you as a COMSCI1 student. If this is an error, you can correct this by contacting an admin."
                    roles.append(self.roles["ca"])
                    roles.append(self.roles["case"])
                elif user_year['course'] == "COMSCI2":
                    rolemsg = "We've automatically determined you as a COMSCI2 student. If this is an error, you can correct this by contacting an admin."
                    roles.append(self.roles["case2"])
                    roles.append(self.roles["case"])
                elif user_year['course'] == "CASE3":
                    rolemsg = "We've automatically determined you as a CASE3 student. If this is an error, you can correct this by contacting an admin."
                    roles.append(self.roles["case3"])
                    roles.append(self.roles["case"])
                elif user_year['course'] == "CASE4":
                    rolemsg = "We've automatically determined you as a CASE4 student. If this is an error, you can correct this by contacting an admin."
                    roles.append(self.roles["case4"])
                    roles.append(self.roles["case"])
                elif user_year['course'] == "CASE":
                    rolemsg = "We've automatically determined you as an Alumni. If this is an error, you can correct this by contacting an admin."
                    roles.append(self.roles["alumni"])
                    roles.append(self.roles["case"])

            # Add roles and greet

            await user.add_roles(
                *roles,
                reason=f"Automatically verified - Email: {user_email}",
            )
            await ctx.send(f"Your account has been verified!\n{rolemsg}")
            await mod.send(
                f"User <@{user.id}> joined the server!",
                allowed_mentions=discord.AllowedMentions(everyone=True),
            )
            await general.send(random.choice(greeting_msgs).format(name=f"<@{user.id}>"))

        else:
            await ctx.send(
                "That code doesn't match the one sent via the email. Try again or request a new code."
            )

    @verify.command(name="other")
    @commands.dm_only()
    async def verify_other(self, ctx, *, message: str):
        """Verification process for external/alumni members."""
        verified = await self.config.user(ctx.author).verified()
        if verified:
            await ctx.send("You are already verified.")
            return
        guild = self.bot.get_guild(713522800081764392)
        channel = guild.get_channel(713522800081764395)
        embed = discord.Embed(description=message, colour=discord.Color.red())
        embed.set_author(name=f"{ctx.author} | {ctx.author.id}", icon_url=ctx.author.avatar_url)
        await channel.send(embed=embed)
        await ctx.send("Your verification request has been sent.")

    @verify.command()
    @commands.admin()
    async def user(self, ctx, type: str, *, user: discord.Member):
        """Verify a user.
        Valid types are internal, external and alumni."""
        if ctx.guild.id != 713522800081764392:
            await ctx.send("This must be used in the CASE++ server.")
        if type.lower() == "external":
            roles = [
                ctx.guild.get_role(713538609017258025),
                ctx.guild.get_role(713538570824187968),
            ]
        elif type.lower() == "internal":
            roles = [ctx.guild.get_role(713538570824187968)]
        elif type.lower() == "alumni":
            roles = [ctx.guild.get_role(713538175456247828)]
        else:
            await ctx.send("Type must be internal or external.")
            return
        await user.add_roles(*roles, reason=f"Manually verified by: {ctx.author}")
        await self.config.user(user).verified_by.set(ctx.author.name)
        await self.config.user(user).verified.set(True)
        await self.config.user(user).email.set(type.title())
        await user.send(f"Your account has been verified on CASE++ by {ctx.author}")
        await ctx.tick()

    @commands.is_owner()
    @commands.command()
    @commands.dm_only()
    async def verifyset(self, ctx, email, password):
        """Credential settings"""
        await self.config.username.set(email)
        await self.config.password.set(password)
        await ctx.tick()

    async def send_email(self, email, code):
        message = EmailMessage()
        message["From"] = "casediscord@gmail.com"
        message["To"] = email
        message["Subject"] = "Discord Verification"
        content = f"Your verification code for the CASE++ server is:\n{code}"
        message.set_content(content)
        await aiosmtplib.send(
            message,
            recipients=[email],
            hostname="smtp.gmail.com",
            port=465,
            username=await self.config.username(),
            password=await self.config.password(),
            use_tls=True,
        )

    @commands.command()
    @commands.admin()
    async def profile(self, ctx, user: discord.Member):
        """Show a users profile information."""
        embed = discord.Embed(color=user.color, title=f"Profile for {user}")
        useri = await self.config.user(user).verified_by()
        verif = await self.config.user(user).verified()
        email = await self.config.user(user).email()
        embed.add_field(name="Verified", value=str(verif))
        if not verif:
            await ctx.send(embed=embed)
            return
        veri_by = useri if useri is not None else "None"
        emaill = email if email is not None else "None"
        embed.add_field(name="Verified By", value=veri_by)
        embed.add_field(name="Email", value=emaill)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.admin()
    async def addwelcomemsg(self, ctx, *, msgtoadd: str):
        """Add welcome message strings to existing list"""

        if "{name}" not in msgtoadd:
            await ctx.send(
                "String must contain the phrase '{name}' to format in place of the users' username."
            )
            return

        await ctx.send(
            "Please confirm that the greeting message is valid with a 'yes' or 'no': \n\n{}".format(
                msgtoadd
            )
        )
        try:
            pred = MessagePredicate.yes_or_no(ctx, user=ctx.author)
            await ctx.bot.wait_for("message", check=pred, timeout=20)
        except asyncio.TimeoutError:
            await ctx.send("Exiting operation.")
            return

        if pred.result:
            async with self.config.welcome_messages() as messages:
                messages.append(msgtoadd)

            await ctx.send("Appended greeting message to existing list successfully!")
        else:
            await ctx.send("Operation cancelled.")

    @commands.command()
    @commands.admin()
    async def listmessages(self, ctx):
        """List welcome messages."""
        msgs = await self.config.welcome_messages()
        if not msgs:
            return await ctx.send("No custom responses available.")
        a = chunks(msgs, 10)
        embeds = []
        i = 0
        for item in a:
            items = []
            for strings in item:
                items.append(f"Reply {i}: {strings}")
                i += 1
            embed = discord.Embed(colour=discord.Color.red(), description="\n".join(items))
            embeds.append(embed)
        if len(embeds) == 1:
            await ctx.send(embed=embeds[0])
        else:
            await menu(ctx, embeds, DEFAULT_CONTROLS)

    @commands.command()
    @commands.admin()
    async def removemessage(self, ctx, index: int):
        """Remove a message by reply ID"""
        async with self.config.welcome_messages() as msgs:
            if index + 1 > len(msgs):
                return await ctx.send("Not a valid ID!")
            msgs.pop(index)
            await ctx.tick()

    @commands.command()
    async def fixroles(self, ctx):
        """Recheck specific roles."""
        async with ctx.typing():
            rolesa = {
                "case4": ctx.guild.get_role(713541403904442438),
                "case3": ctx.guild.get_role(713539660936118282),
                "case2": ctx.guild.get_role(713538655817564250),
                "ca": ctx.guild.get_role(713541535085494312),
                "case": ctx.guild.get_role(713538335984975943),
            }
            msg = ""
            user = ctx.message.author

            if not await self.config.user(user).verified():
                return await ctx.send("Unfortunately we do not have your account data on record. Please re-verify or contact an Admin for roles.")
            email = await self.config.user(user).email()

            user_year = await self.get_course_year(email.lower())
            roles = []

            if type(user_year) != dict:
                msg = ""
            else:
                if user_year['course'] == "COMSCI1":
                    roles.append(rolesa["ca"])
                    roles.append(rolesa["case"])
                elif user_year['course'] == "COMSCI2":
                    roles.append(rolesa["case2"])
                    roles.append(rolesa["case"])
                elif user_year['course'] == "CASE3":
                    roles.append(rolesa["case3"])
                    roles.append(rolesa["case"])
                elif user_year['course'] == "CASE4":
                    roles.append(rolesa["case4"])
                    roles.append(rolesa["case"])

            if roles:
                removed_roles = [
                    role
                    for role in user.roles
                    if role not in roles and role in rolesa.values()
                ]
                await user.remove_roles(*removed_roles)
                await user.add_roles(*roles, reason="updated")
                msg += (
                    f"Updated {user}s roles - New roles: {', '.join([x.name for x in roles])}\n"
                )
            if msg:
                await ctx.send(msg)
            else:
                await ctx.send("An error occured while fetching your data. Please contact an Admin.")

    @commands.command()
    @commands.admin()
    async def recheckall(self, ctx):
        """Recheck all users roles."""
        async with ctx.typing():
            rolesa = {
                "case4": ctx.guild.get_role(713541403904442438),
                "case3": ctx.guild.get_role(713539660936118282),
                "case2": ctx.guild.get_role(713538655817564250),
                "ca": ctx.guild.get_role(713541535085494312),
                "case": ctx.guild.get_role(713538335984975943),
            }
            msg = ""
            for user in ctx.guild.members:
                if not await self.config.user(user).verified():
                    continue
                email = await self.config.user(user).email()

                # Check a the SoC API for course
                user_year = await self.get_course_year(email.lower())
                roles = []

                if type(user_year) != dict:
                    msg = ""
                else:
                    if user_year['course'] == "COMSCI1":
                        roles.append(rolesa["ca"])
                        roles.append(rolesa["case"])
                    elif user_year['course'] == "COMSCI2":
                        roles.append(rolesa["case2"])
                        roles.append(rolesa["case"])
                    elif user_year['course'] == "CASE3":
                        roles.append(rolesa["case3"])
                        roles.append(rolesa["case"])
                    elif user_year['course'] == "CASE4":
                        roles.append(rolesa["case4"])
                        roles.append(rolesa["case"])

                if roles:
                    removed_roles = [
                        role
                        for role in user.roles
                        if role not in roles and role in rolesa.values()
                    ]
                    await user.remove_roles(*removed_roles)
                    await user.add_roles(*roles, reason="updated")
                    msg += (
                        f"Updated {user}s roles - New roles: {', '.join([x.name for x in roles])}\n"
                    )
            if msg:
                for page in pagify(msg):
                    await ctx.send(page)
            else:
                await ctx.send("No users updated")
