import discord
from discord.ext import commands

from constants import *

from __main__ import log, cogsReady

class Staff(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_ready(self):
        log.debug("Staff Cog is ready", flush=True)
        cogsReady["staff"] = True
    
    @commands.command()
    @commands.has_any_role(UNIT_STAFF)
    async def promote(self, ctx, member: discord.Member):
        """
        Promote a member to the next rank
        """
        
        guild = self.bot.get_guild(SERVER)
        for role in member.roles:
            if role.id in PROMOTIONS:
                newRole = guild.get_role(PROMOTIONS[role.id])
                # Turn promotions to operator into promotions to technician if member is SME
                if newRole.id == OPERATOR:
                    isSME = False
                    for role_ in member.roles:
                        if role_.id in SME_ROLES:
                            isSME = True
                            break
                    if isSME:
                        newRole = guild.get_role(TECHNICIAN)
                log.info(f"Promoting {member.display_name} from {role} to {newRole}")
                await member.remove_roles(role)
                await member.add_roles(newRole)
                break
        else:
            log.warning(f"No promotion possible for {member.display_name}")

    @commands.command()
    @commands.has_any_role(UNIT_STAFF)
    async def demote(self, ctx, member: discord.Member):
        """
        Demote a member to the previous rank
        """
        
        guild = self.bot.get_guild(SERVER)
        for role in member.roles:
            if role.id in DEMOTIONS:
                newRole = guild.get_role(DEMOTIONS[role.id])
                log.info(f"Demoting {member.display_name} from {role} to {newRole}")
                await member.remove_roles(role)
                await member.add_roles(newRole)
                break
        else:
            log.warning(f"No demotion possible for {member.display_name}")

def setup(bot):
    bot.add_cog(Staff(bot))