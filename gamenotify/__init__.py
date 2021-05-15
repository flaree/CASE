from .gamenotify import Gamenotify

def setup(bot):
    bot.add_cog(Gamenotify(bot))