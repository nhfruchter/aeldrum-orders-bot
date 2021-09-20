import discord
import os
import re
from sqlitedict import SqliteDict

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
    if message.channel.type != discord.ChannelType.private and message.guild.id != int(
        AELDRUM_SERVER_ID
    ):
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
            "Are you a member of the Aeldrum server? Member ID: "
            + str(message.author.id)
        )
        return

    async def _help():
        await message.channel.send(HELP_TEXT)

    async def _affiliation():
        cmd = message.content.split()
        has_affil = requestor.id in USER_SPECIFIED_AFFIL

        if len(cmd) < 2 or cmd[0] != AFFIL_PREFIX:
            return await _help()

        if cmd[1] == "clear":
            await message.add_reaction("✅")

            # Only clear if there's actually something stored
            if has_affil:
                del USER_SPECIFIED_AFFIL[requestor.id]
            return
        elif cmd[1] == "check":
            await message.add_reaction("✅")

            # Fetch affiliation or display discord top role
            my_affil = USER_SPECIFIED_AFFIL.get(requestor.id)
            discord_affil = requestor.top_role

            if my_affil:
                await message.channel.send(
                    "%s is sending orders from %s *(custom)*"
                    % (requestor.display_name, my_affil)
                )
            elif discord_affil:
                await message.channel.send(
                    "%s is sending orders from %s *(Discord)*"
                    % (requestor.display_name, discord_affil)
                )
            else:
                await message.channel.send(
                    "%s has no associated faction" % requestor.display_name
                )
        else:
            # Probably setting a default here - reconstruct the string
            new_affil = " ".join(cmd[1:])
            USER_SPECIFIED_AFFIL[requestor.id] = new_affil

            if has_affil:
                await message.add_reaction("🔄")
            else:
                await message.add_reaction("✅")

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
                await message.channel.send(
                    "%s is sending orders for turn **%s**"
                    % (requestor.display_name, specified_turn)
                )
            elif default_turn:
                await message.channel.send(
                    "%s is sending orders for turn **%s** (default)"
                    % (requestor.display_name, default_turn)
                )
            else:
                await message.channel.send(
                    "%s is sending orders **without** turn data"
                    % requestor.display_name
                )
            return
        elif turn_cmd[1] == "default":
            if len(turn_cmd) != 3:
                return await _help()

            if turn_cmd[2] == "clear":
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

    async def order(order_content):
        files = await files_from_attachments(message.attachments)

        # Get turn, if present
        order_turn = (
            USER_SPECIFIED_TURNS.get(requestor.id)
            or USER_SPECIFIED_TURNS.get(DEFAULT_USER)
            or ""
        )

        # Affiliation/title for embed
        # Order of precedence: !sendorder[name] > !faction name > requestor.top_role
        
        affiliation = USER_SPECIFIED_AFFIL.get(requestor.id) or requestor.top_role
        content = order_content

        # String hacking to get the first set of brackets: find first bracket
        # ...then find the next close bracket, get the stuff inside
        # ...and remove
        
        if order_content.startswith("["):
            affiliation = order_content[1:order_content.find("]")]
            content = content[len(affiliation)+2:].strip()

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
                " ".join([a.url for a in message.attachments]) or "",
            ]
            logging.debug("Sent update to sheet %s" % update_row)
            sheetslogger.update(LOG_TO_SHEET, update_row)

    async def _orders():
        # Match command prefix using word boundary.
        # Note: This misses edge cases (like !!sendorder)... pray for sanity
        CMD_PATTERN = r"%s\b" % CMD_PREFIX

        # Ignore leading '' caused by matching !sendorder prefix
        for order_content in re.split(CMD_PATTERN, message.content)[1:]:
            await order(order_content.strip())

    # ...and the functions that parse the command
    commands = {
        CMD_PREFIX: _orders,
        TURN_PREFIX: _turn,
        AFFIL_PREFIX: _affiliation,
        HELP_PREFIX: _help,
    }

    for matcher, fn in commands.items():
        if message.content.startswith(matcher):
            return await fn()

    # If user sends invalid command to bot, send help text.
    if message.channel.type == discord.ChannelType.private:
        return await _help()


if __name__ == "__main__":
    import logging
    import datetime
    
    # Environment variables needed
    DISCORD_TOKEN = os.getenv("TOKEN")
    ORDERS_CHANNEL_ID = os.getenv("ORDERS_CHANNEL_ID")
    AELDRUM_SERVER_ID = os.getenv("AELDRUM_SERVER_ID")
    DEBUG = os.getenv("DEBUG")
    _required = (DISCORD_TOKEN, ORDERS_CHANNEL_ID, AELDRUM_SERVER_ID)

    # Configurable stuff
    # Google Sheet ID or False if you want it off
    LOG_TO_SHEET = "1RHM0_hfx2pOs6_TrWzCwcN6QLBlSPl42ul6E_UWbR0Y"

    CMD_PREFIX = "!sendorder"
    AFFIL_PREFIX = "!faction"
    TURN_PREFIX = "!turn"
    HELP_PREFIX = "!plshelp"

    # Read help text from the file
    with open("help_text.md") as f:
        HELP_TEXT = f.read()

    # Debug flag
    if DEBUG:
        HELP_TEXT = "host [%s %s] %s" % (
            os.uname().nodename,
            os.uname().release,
            HELP_TEXT,
        )
        logging.basicConfig(filename="aeldrum-ordersbot.log", level=logging.DEBUG)
    else:
        logging.basicConfig(filename="aeldrum-ordersbot.log", level=logging.INFO)        

    # Holding for user-keyed preferences.  Default value uses user 0.
    DEFAULT_USER = 0
    USER_SPECIFIED_TURNS = SqliteDict("./prefs_turns.sqlite", autocommit=True)
    USER_SPECIFIED_AFFIL = SqliteDict("./prefs_affil.sqlite", autocommit=True)

    # All env vars must be present
    if not all(_required):
        print("Please specify TOKEN, AELDRUM_SERVER_ID, and ORDERS_CHANNEL_ID")
    else:
        print("Started bot at %s" % datetime.datetime.now())

        if LOG_TO_SHEET:
            import sheetslogger
            logging.info("Logging to Google Sheet ID %s" % LOG_TO_SHEET)
            try:
                sheetslogger.update(LOG_TO_SHEET, [datetime.datetime.now().strftime("%x %X"), "Bot enabled", "", "", "", ""])
            except:
                raise Exception("There was an error communicating with Google Sheets.")                    

        client.run(DISCORD_TOKEN)
