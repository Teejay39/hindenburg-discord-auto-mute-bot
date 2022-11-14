import os

import discord
import dotenv
from discord.ext import commands

from amongus.embed import addConnection
from db.DbConnection import DbConnection

dotenv.load_dotenv()

class SelectUserName(discord.ui.Select):
    def __init__(self, options: list, db_connection: DbConnection, code: str, result, channel: discord.VoiceChannel,
                 member: discord.Member, origin_interaction: discord.Interaction):
        super().__init__(
            placeholder="Select",
            min_values=1,
            max_values=1,
            options=options)
        self.db_connection = db_connection
        self.code = code
        self.result = result
        self.channel = channel
        self.member = member
        self.origin_interaction = origin_interaction

    async def callback(self, interaction):
        await self.origin_interaction.edit_original_response(view=None, delete_after=5)
        await interaction.response.send_message(content=f"{self.values[0]} is your Among Us name")

        embed = discord.Embed(title="Among Us Auto Mute")
        embed.add_field(name="Code", value=f"`{self.code}`")
        embed.add_field(name="Channel", value=self.channel.mention)
        embed.add_field(name="Host", value=self.member.mention)
        embed.add_field(name="Player connected", value=f"1/{len(self.result)}", inline=False)
        i = 0
        for row in self.result:
            i = i + 1
            if row[0] == self.values[0]:
                embed.add_field(name=i, value=f"{row[0]} [{self.member.mention}]")
                continue
            embed.add_field(name=i, value=row[0])

        interaction_message: discord.InteractionMessage = await interaction.edit_original_response(content=None,
                                                                                                   embed=embed,
                                                                                                   view=ViewUserButtons(db_connection=self.db_connection, code=self.code))
        sql = f"UPDATE players SET discord_message_id = {interaction_message.id}, discord_voice_id = {self.channel.id}, discord_user_id = {self.member.id}, is_host = TRUE WHERE roomcode = '{self.code}' and username = '{self.values[0]}'"
        self.db_connection.execute(sql)
        sql = f"UPDATE players SET discord_message_id = {interaction_message.id}, discord_voice_id = {self.channel.id} WHERE roomcode = '{self.code}' and is_host = FALSE"
        self.db_connection.execute(sql)

# class ViewUserName(discord.ui.View):
#     def __init__(self, db_connection: DbConnection, code: str):
#         super().__init__(timeout=30)

class createButton(discord.ui.Button["ViewUserButtons"]):
    def __init__(self, num: int, row: int):
        super().__init__(label=str(num), row=row)
        
    async def callback(self, interaction: discord.Interaction):
        view: ViewUserButtons = self.view
        msg = await addConnection(self.db_connection, num, interaction)
        await interaction.response.send_message(content=msg, ephemeral=True, delete_after=10 view=view)

class ViewUserButtons(discord.ui.View):
    def __init__(self, db_connection: DbConnection, code: str):
        super().__init__(timeout=None)
        self.db_connection = db_connection
        self.code = code
        self.maxplayers = self.db_connection.execute_list(f"SELECT maxplayers FROM players WHERE roomcode = '{self.code}' LIMIT 1")
        for i in range(0, self.maxplayers):
            num = i + 1
            row = 0
            if num > 5 and num < 11:
                row = 1
            elif num > 10:
                row = 2
            self.add_item(createButton(num, row))
        
    async def on_timeout(self):
        await self.message.edit(content="OVER", view=self)
        print("OVER OVER OVER")

class Setup(commands.Cog):
    def __init__(self, bot: commands.Bot, db_connection: DbConnection):
        self.bot = bot
        self.db_connection = db_connection

    @commands.slash_command(name="setup", description="Setup for Auto Mute")
    @discord.default_permissions(connect=True)
    async def setup(self, ctx,
                    room_code: discord.Option(str, name="roomcode", description="Roomcode of your Among Us Lobby",
                                              max_length=6)):
        member: discord.Member = ctx.author
        if member.voice is None:
            await ctx.send_response(content="You are not in a voice Channel", ephemeral=True, delete_after=10)
            return

        channel: discord.VoiceChannel = member.voice.channel

        code: str = room_code
        code = code.upper()
        if ";" in code or "'" in code or "`" in code or "DROP" in code:
            await ctx.respond("Don't try it")
            return

        sql = f"SELECT username FROM players WHERE roomcode = '{code}'"
        result = self.db_connection.execute_list(sql)

        if len(result) < 1:
            await ctx.send_response(content=f"No Lobby with room code {code} found!", ephemeral=True, delete_after=10)
            return

        sql = f"SELECT discord_user_id FROM players WHERE roomcode = '{code}' and is_host = TRUE"
        result2 = self.db_connection.execute_list(sql)

        if len(result2) > 0:
            if member.id != result2[0][0]:
                await ctx.send_response(content=f"You are not the Host of the Lobby", ephemeral=True, delete_after=10)
                return

            sql = f"SELECT discord_message_id FROM players WHERE roomcode = '{code}' and is_host = TRUE"
            result2 = self.db_connection.execute_list(sql)
            msg: discord.Message = self.bot.get_message(result2[0][0])
            await msg.edit(view=None)
            await msg.delete(delay=5)

        options: list = list()
        for row in result:
            select_option = discord.SelectOption(
                label=row[0]
            )
            options.append(select_option)

        view_select = discord.ui.View(timeout=60)
        interaction: discord.Interaction = await ctx.send_response(content="Select your Among Us Username",
                                                                   ephemeral=True,
                                                                   view=view_select)

        select = SelectUserName(options, self.db_connection, code, result, channel, member, interaction)
        view_select.add_item(select)
        await interaction.edit_original_response(view=view_select)
