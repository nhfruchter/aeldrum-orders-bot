import discord
import os
import re

intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)


async def files_from_attachments(attachments):
    """Extract each individual file from a message so it can be moved over by the bot."""

    files = []
    for attachment in attachments:
        files.append(await attachment.to_file())
    return files


async def get_default_role(member_id):
    server = client.get_guild(int(AELDRUM_SERVER_ID))
    member = server.get_member(member_id)
    return member.top_role


@client.event
async def on_message(message):
    """Handle each incoming message."""

    # Ignore self
    if message.author == client.user:
        return

    # Accept requests only from valid sources
    if message.channel.type != discord.ChannelType.private and message.guild.id != int(
        AELDRUM_SERVER_ID
    ):
        return

    # Identify the channel that orders will be sent to
    order_channel_id = ORDERS_CHANNEL_ID
    order_channel = client.get_channel(int(order_channel_id))

    # Error message if order channel is not set
    if order_channel == None:
        await message.channel.send("Could not find channel " + order_channel_id)
        logging.warning("Unable to find channnel " + order_channel_id)

    async def _help():
        await message.channel.send(HELP_TEXT)
    
    async def _turn():
        turn_label = message.content.split(TURN_PREFIX)

        # If the user just wants to clear their turn, do so and exit
        if turn_label[1].strip() == "clear":
            await message.add_reaction("✅")
            # Only clear if there's actually something stored
            if message.author.id in USER_SPECIFIED_TURNS:
                del USER_SPECIFIED_TURNS[message.author.id]
            return
        elif turn_label[1].strip() == "check":
          await message.add_reaction("✅")
          specified_turn = USER_SPECIFIED_TURNS.get(message.author.id)
          if specified_turn:
              await message.channel.send("%s is sending orders for turn **%s**" % (message.author.display_name, specified_turn))
          else:
              await message.channel.send("%s is sending orders **without** turn data" % message.author.display_name)
          return

        # Map the user's specified turn label to the user - so different users
        # are able to send different things in the same channel.
        if len(turn_label) == 2:
            try:
                # Get the turn number
                turn_label = int(turn_label[1].strip())

                if message.author.id in USER_SPECIFIED_TURNS:
                    # If the user has specified a turn already, update it
                    await message.add_reaction("🔄")
                else:
                    # Else confirm it
                    await message.add_reaction("✅")

                USER_SPECIFIED_TURNS[message.author.id] = turn_label

            except:
                await message.channel.send("Turns must be an integer > 0.")
                await message.add_reaction("❌")
        else:
            await message.channel.send("Sorry, something went wrong.")
            await message.add_reaction("❌")        

    async def _orders():
        parsed = re.findall(CMD_ORDER, message.content, re.IGNORECASE + re.MULTILINE)

        if len(parsed):
            # args[0] = blank if no alt affiliation, args[1] = message
            args = parsed[0]
            content = args[1].strip()

            # Grab the files, if any
            files = await files_from_attachments(message.attachments)

            # Affiliation/title for embed: either from role or specified in brackets
            # !sendorder foo => role, !sendorder[something else] foo => "something else"
            affiliation = (
                args[0].replace("[", "").replace("]", "")
                if args[0]
                else getattr(
                    message.author, "top_role", await get_default_role(message.author.id)
                )
            )

            # Get turn, if present
            order_turn = USER_SPECIFIED_TURNS.get(message.author.id) or ""

            # Create fancy Discord embed
            title = "Order from %s" % affiliation
            if order_turn:
                title = "*[Turn %s]* " % order_turn + title

            out_message = discord.Embed(title=title, description=content)

            # Set embed author to sender
            out_message.set_author(
                name=message.author.display_name, icon_url=message.author.avatar_url
            )

            logging.debug(
                "%s, %s, %s, files: %s",
                message.author.display_name,
                affiliation,
                content,
                len(files),
            )

            await order_channel.send(embed=out_message, files=files)
            await message.add_reaction("👍")
            
            if LOG_TO_SHEET:
                # Currently: Timestamp, Turn, Faction, Author, Content,	Attachments
                update_row = [
                    datetime.datetime.now().strftime("%x %X"),
                    order_turn,
                    str(affiliation),
                    message.author.display_name,
                    content,
                    " ".join([a.url for a in message.attachments]) or ""
                ]
                logging.debug("Sent update to sheet %s" % update_row)
                sheetslogger.update(LOG_TO_SHEET, update_row)
                
    # Register bot commands through the patterns needed to match their flags            
    CMD_ORDER = r"^" + CMD_PREFIX + r"(\[[^\]]*])? (.+)"
    CMD_TURN = r"^" + TURN_PREFIX
    CMD_HELP = r"^" + HELP_PREFIX

    # ...and the functions that parse the command
    commands = {
        CMD_ORDER: _orders,
        CMD_TURN: _turn,
        CMD_HELP: _help,
    }

    for matcher, fn in commands.items():
        is_match = re.findall(matcher, message.content, re.IGNORECASE + re.MULTILINE)
        if len(is_match):
            await fn()
            return

    # If user sends invalid command to bot, send help text.
    if message.channel.type == discord.ChannelType.private:
      return await _help()

if __name__ == "__main__":
    import logging
    import datetime

    logging.basicConfig(filename="aeldrum-ordersbot.log", level=logging.DEBUG)
    
    # Environment variables needed
    DISCORD_TOKEN = os.getenv("TOKEN")
    ORDERS_CHANNEL_ID = os.getenv("ORDERS_CHANNEL_ID")
    AELDRUM_SERVER_ID = os.getenv("AELDRUM_SERVER_ID")
    _required = (DISCORD_TOKEN, ORDERS_CHANNEL_ID, AELDRUM_SERVER_ID)

    # Configurable stuff
    # Google Sheet ID or False if you want it off
    LOG_TO_SHEET = "1RHM0_hfx2pOs6_TrWzCwcN6QLBlSPl42ul6E_UWbR0Y"
    
    CMD_PREFIX = "!sendorder"
    TURN_PREFIX = "!turn"
    HELP_PREFIX = "!plshelp"

    HELP_TEXT = """:scroll: **Aeldrum Orders Bot** :pencil2:
    
• **!sendorder ...** will send an order to the DM channel with all text and attachments. Orders are attributed to your faction as specified by Discord role.
• **!sendorder[Another Faction] ...** lets attribute your order to a different faction.

• **!turn *n*  **specifies a turn number which will appear with your order. Turns are attached to your user, not your factions or your channels. 
• **!turn clear** will remove turn data associated with your user. 
• **!turn check** will tell you what turn you've specified, if any.
    
Happy backstabbing!"""

    # Holding for !turn commands
    USER_SPECIFIED_TURNS = {}

    # All env vars must be present
    if not all(_required):
        print("Please specify TOKEN, AELDRUM_SERVER_ID, and ORDERS_CHANNEL_ID")
    else:
        print("Started bot at %s" % datetime.datetime.now())
        
        if LOG_TO_SHEET:
            import sheetslogger
            
        client.run(DISCORD_TOKEN)
