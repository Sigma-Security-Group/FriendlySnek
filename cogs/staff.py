import discord
from discord.ext import commands

from constants import *

from __main__ import log, cogsReady, DEBUG
if DEBUG:
    from constants.debug import *

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
    async def demote(self, ctx, *, member: discord.Member):
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
    
    @commands.command()
    @commands.has_any_role(UNIT_STAFF)
    async def searchModLogs(self, ctx, *, searchTerm):
        """
        Demote a member to the previous rank
        """
        member = None
        for member_ in self.bot.get_guild(SERVER).members:
            if searchTerm.replace("<", "").replace("@", "").replace("!", "").replace(">", "").isdigit() and int(searchTerm.replace("<", "").replace("@", "").replace("!", "").replace(">", "")) == member_.id:
                member = member_
                break
            if searchTerm == member_.display_name or searchTerm == member_.name or searchTerm == member_.mention or searchTerm == member_.mention.replace("<@", "<@!") or searchTerm == member_.mention.replace("<@!", "<@") or (searchTerm.isdigit() and int(searchTerm) == member_.discriminator):
                member = member_
                break
            if searchTerm.lower() == member_.display_name.lower() or searchTerm.lower() == member_.name.lower() or searchTerm.lower() == member_.mention.lower() or searchTerm.lower() == member_.mention.lower().replace("<@", "<@!") or searchTerm.lower() == member_.mention.lower().replace("<@!", "<@") or (searchTerm.isdigit() and int(searchTerm) == member_.discriminator):
                member = member_
                break
            if searchTerm in member_.display_name or searchTerm in member_.name or searchTerm in member_.mention or searchTerm in member_.mention.replace("<@", "<@!") or searchTerm in member_.mention.replace("<@!", "<@"):
                member = member_
            if searchTerm.lower() in member_.display_name.lower() or searchTerm.lower() in member_.name.lower() or searchTerm.lower() in member_.mention.lower() or searchTerm.lower() in member_.mention.lower().replace("<@", "<@!") or searchTerm.lower() in member_.mention.lower().replace("<@!", "<@"):
                member = member_
        if member is None:
            log.warning(f"No member found for search term: {searchTerm}")
            log.debug(f"Searching Moderation Logs for search term: {searchTerm}")
            messageLinksList = []
            numMessages = 0
            async for message in self.bot.get_channel(MODERATION_LOG).history(limit=None):
                numMessages += 1
                if searchTerm.lower() in message.content.lower():
                    messageLinksList.append(message.jump_url)
            log.debug(f"Checked {numMessages} message{'s' * (numMessages != 1)}")
            if len(messageLinksList) > 0:
                messageLinks = "\n".join(messageLinksList[::-1])
                await self.bot.get_channel(STAFF_CHAT).send(f"Moderation Logs related to search term: {searchTerm}\n{messageLinks}")
            else:
                await self.bot.get_channel(STAFF_CHAT).send(f"No Moderation Logs related to search term: {searchTerm}")
        else:
            log.debug(f"Searching Moderation Logs for {member.display_name}({member.name}#{member.discriminator})")
            messageLinksList = []
            numMessages = 0
            async for message in self.bot.get_channel(MODERATION_LOG).history(limit=None):
                numMessages += 1
                if member.display_name.lower() in message.content.lower() or member.name.lower() in message.content.lower() or member.mention.lower() in message.content.lower() or member.mention.lower().replace("<@", "<@!") in message.content.lower() or member.mention.lower().replace("<@!", "<@") in message.content.lower() or str(member.id) in message.content:
                    messageLinksList.append(message.jump_url)
            log.debug(f"Checked {numMessages} message{'s' * (numMessages != 1)}")
            if len(messageLinksList) > 0:
                messageLinks = "\n".join(messageLinksList[::-1])
                await self.bot.get_channel(STAFF_CHAT).send(f"Moderation Logs related to {member.display_name}({member.name}#{member.discriminator}):\n{messageLinks}")
            else:
                await self.bot.get_channel(STAFF_CHAT).send(f"No Moderation Logs related to {member.display_name}({member.name}#{member.discriminator})")

def setup(bot):
    bot.add_cog(Staff(bot))