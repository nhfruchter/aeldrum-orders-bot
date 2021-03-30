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

@client.event
async def on_message(message):
    """Handle each incoming message."""

    # Ignore self
    if message.author == client.user:
        return

    # Accept requests only from valid sources
    if (message.channel.type != discord.ChannelType.private and 
        message.guild.id != int(AELDRUM_SERVER_ID)):
        return

    # Identify the channel that orders will be sent to
    order_channel_id = ORDERS_CHANNEL_ID
    order_channel = client.get_channel(int(order_channel_id))

    # Error message if order channel is not set
    if order_channel == None:
        await message.channel.send("Could not find order channel " + order_channel_id)
        logging.warning("Unable to find order channnel " + order_channel_id)

    requestor = client.get_guild(int(AELDRUM_SERVER_ID)).get_member(message.author.id)
    if requestor == None:
      await message.channel.send(
        "Are you a member of the Aeldrum server? Member ID: " + str(message.author.id))
      return

    async def _help():
        await message.channel.send(HELP_TEXT)
    
    async def _turn():
        turn_cmd = message.content.split()
        if len(turn_cmd) < 2 or turn_cmd[0] != TURN_PREFIX:
          return await _help()
        
        # If the user just wants to clear their turn, do so and exit
        if turn_cmd[1] == "clear":
            await message.add_reaction("✅")
            # Only clear if there's actually something stored
            if requestor.id in USER_SPECIFIED_TURNS:
                del USER_SPECIFIED_TURNS[requestor.id]
            return
        elif turn_cmd[1] == "check":
          await message.add_reaction("✅")
          specified_turn = USER_SPECIFIED_TURNS.get(requestor.id)
          default_turn = USER_SPECIFIED_TURNS.get(DEFAULT_USER)
          if specified_turn:
            await message.channel.send("%s is sending orders for turn **%s**" % (requestor.display_name, specified_turn))
          elif default_turn:
            await message.channel.send("%s is sending orders for turn **%s** (default)" % (requestor.display_name, default_turn))
          else:
              await message.channel.send(
                "%s is sending orders **without** turn data" % requestor.display_name)
          return
        elif turn_cmd[1] == "default":
          if len(turn_cmd) != 3:
            return await _help()

          if (turn_cmd[2] == "clear"):
            await message.add_reaction("✅")
            if DEFAULT_USER in USER_SPECIFIED_TURNS:
              del USER_SPECIFIED_TURNS[DEFAULT_USER]
            return
        
          try:
            # Get the turn number
            turn_label = int(turn_cmd[2])
            if DEFAULT_USER in USER_SPECIFIED_TURNS:
               # If the user has specified a turn already, update it
               await message.add_reaction("🔄")
               USER_SPECIFIED_TURNS[DEFAULT_USER] = turn_label
            else:
               # Else confirm it
               await message.add_reaction("✅")
               USER_SPECIFIED_TURNS[DEFAULT_USER] = turn_label
          except:
            await message.channel.send("Turns must be an integer > 0.")
            await message.add_reaction("❌") 
        else:
          if len(turn_cmd) != 2:
            return await _help()
        
          try:
           # Get the turn number
           turn_label = int(turn_cmd[1])

           if requestor.id in USER_SPECIFIED_TURNS:
             # If the user has specified a turn already, update it
             await message.add_reaction("🔄")
           else:
             # Else confirm it
             await message.add_reaction("✅")

             USER_SPECIFIED_TURNS[requestor.id] = turn_label

          except:
            await message.channel.send("Turns must be an integer > 0.")
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
                else requestor.top_role
            )

            # Get turn, if present
            order_turn = (
              USER_SPECIFIED_TURNS.get(requestor.id) or 
              USER_SPECIFIED_TURNS.get(DEFAULT_USER) or ""
            )

            # Create fancy Discord embed
            title = "Order from %s" % affiliation
            if order_turn:
                title = "*[Turn %s]* " % order_turn + title

            out_message = discord.Embed(title=title, description=content)

            # Set embed author to sender
            out_message.set_author(
                name=requestor.display_name, icon_url=requestor.avatar_url
            )

            logging.debug(
                "%s, %s, %s, files: %s",
                requestor.display_name,
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
                    requestor.display_name,
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
            return await fn()

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
• **!turn default *n* **specifies a default turn that applies to all users without an explicitly set turn.
• **!turn default clear** removes turn data associated with the default turn.

    
Happy backstabbing!"""

    # Holding for !turn commands.  Default value uses user 0.
    DEFAULT_USER = 0
    USER_SPECIFIED_TURNS = {}

    # All env vars must be present
    if not all(_required):
        print("Please specify TOKEN, AELDRUM_SERVER_ID, and ORDERS_CHANNEL_ID")
    else:
        print("Started bot at %s" % datetime.datetime.now())
        
        if LOG_TO_SHEET:
            import sheetslogger
            
        client.run(DISCORD_TOKEN)
