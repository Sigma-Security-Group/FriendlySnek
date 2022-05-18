import discord
from discord import app_commands
from discord.ext import commands

MY_GUILD = discord.Object(id=864441968776052747)

class MyCog(commands.Cog):
	def __init__(self, bot: commands.Bot) -> None:
		self.bot = bot
    
	@app_commands.command(name="command-1")
	@app_commands.guilds(MY_GUILD)
	async def my_command(self, interaction: discord.Interaction) -> None:
		""" /command-1 """
		await interaction.response.send_message("Hello from command 1!", ephemeral=True)

	@app_commands.command(name="command-2")
	@app_commands.guilds(MY_GUILD)
	async def my_private_command(self, interaction: discord.Interaction) -> None:
		""" /command-2 """
		await interaction.response.send_message("Hello from private command!", ephemeral=True)

async def setup(bot: commands.Bot) -> None:
	await bot.add_cog(MyCog(bot))
