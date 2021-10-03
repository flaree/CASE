from .autotimetable import AutoTimetable


def setup(bot):
    n = AutoTimetable(bot)
    bot.add_cog(n)
