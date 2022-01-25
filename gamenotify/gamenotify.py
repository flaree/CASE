import logging

import discord
from redbot.core import Config, bank, commands
from redbot.core.utils.chat_formatting import escape, humanize_list, humanize_number, inline

log = logging.getLogger("red.flare.gamenotify")


class Gamenotify(commands.Cog):
    """Sub to game pings"""

    __version__ = "0.0.1"

    def format_help_for_context(self, ctx):
        pre_processed = super().format_help_for_context(ctx)
        return f"{pre_processed}\nCog Version: {self.__version__}"

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 95932766180343808, force_registration=True)
        self.config.register_guild(games={})

    @commands.cooldown(1, 300, commands.BucketType.user)
    @commands.command()
    @commands.guild_only()
    async def notify(self, ctx, *, game: str):
        """Ping a game."""
        game = game.lower()
        games = await self.config.guild(ctx.guild).games()
        if game not in games:
            await ctx.send(
                f"That game doesn't exist, did you mean one of the following? {humanize_list(list(map(inline, games.keys())))}"
            )
            return
        if ctx.author.id not in games[game]:
            await ctx.send(f"You must be signed up for {game} pings in order to notify it's other members.")
            return
        users = []
        for user in games[game]:
            obj = ctx.guild.get_member(user)
            if obj is None:
                continue
            users.append(obj.mention)
        if not users:
            await ctx.send("Nobody is signed up for pings for that game.")
            return
        msg = f"{escape(game, mass_mentions=True).title()}: {','.join(users)}"
        await ctx.send(msg)

    @commands.command()
    @commands.guild_only()
    async def addping(self, ctx, *, game: str):
        """Add/remove a ping for a game."""
        game = game.lower()
        async with self.config.guild(ctx.guild).games() as games:
            if game in games:
                if ctx.author.id in games[game]:
                    games[game].remove(ctx.author.id)
                    await ctx.send("You have been removed from pings for this game.")
                else:
                    games[game].append(ctx.author.id)
                    await ctx.send(
                        f"You have been added to the ping list for {escape(game, mass_mentions=True)}."
                    )
            else:
                games[game] = []
                games[game].append(ctx.author.id)
                await ctx.send(
                    "That game has now been created and you have added to the ping list"
                )

    @commands.command()
    @commands.guild_only()
    async def listgames(self, ctx):
        """List games for notifying."""
        games = await self.config.guild(ctx.guild).games()
        if not games:
            await ctx.send("No games are registered in this guild silly.")
            return
        new_games = [game for game in games if games[game]]
        if not new_games:
            await ctx.send("No games are registered in this guild silly.")
            return
        await ctx.send(f"Current registered games: {humanize_list(list(map(inline, new_games)))}")

    @commands.command()
    @commands.guild_only()
    async def listpings(self, ctx, *, game: str):
        """List pings for a game."""
        games = await self.config.guild(ctx.guild).games()
        if game.lower() not in games:
            await ctx.send("That game isn't registered for pings.")
            return
        users = []
        for user in games[game.lower()]:
            obj = ctx.guild.get_member(user)
            if obj is not None:
                users.append(str(obj))
        if not users:
            await ctx.send(f"No valid users registered for {game}.")
        await ctx.send(
            f"Current registered users for {game}: {humanize_list(list(map(inline, users)))}"
        )

    @commands.command()
    @commands.guild_only()
    @commands.mod()
    async def delgame(self, ctx, *, game: str):
        """Deletea game."""
        game = game.lower()
        async with self.config.guild(ctx.guild).games() as games:
            if game in games:
                del games[game]
                await ctx.send("That game has now deleted.")
            else:
                await ctx.send("That game does not exist.")
