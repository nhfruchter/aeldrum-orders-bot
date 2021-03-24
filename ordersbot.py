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

    # Only respond to messages starting with the command flags
    if message.content.startswith(ROUND_PREFIX):
        round_label = message.content.split(ROUND_PREFIX)

        # If the user just wants to clear their round, do so and exit

        if round_label[1].strip() == "clear":
            await message.add_reaction("✅")
            # Only clear if there's actually something stored
            if message.author.id in USER_SPECIFIED_ROUNDS:
                del USER_SPECIFIED_ROUNDS[message.author.id]
            return

        # Map the user's specified round label to the user - so different users
        # are able to send different things in the same channel.
        if len(round_label) == 2:
            try:
                # Get the round number
                round_label = int(round_label[1].strip())

                if message.author.id in USER_SPECIFIED_ROUNDS:
                    # If the user has specified a round already, update it
                    await message.add_reaction("🔄")
                else:
                    # Else confirm it
                    await message.add_reaction("✅")

                USER_SPECIFIED_ROUNDS[message.author.id] = round_label

            except:
                await message.channel.send("Rounds must be an integer > 0.")
                await message.add_reaction("❌")
        else:
            await message.channel.send("Sorry, something went wrong.")
            await message.add_reaction("❌")

    # Handle sending orders
    CMD_RE = r"^" + CMD_PREFIX + r"(\[[^\]]*])? (.+)"
    parsed = re.findall(CMD_RE, message.content, re.IGNORECASE + re.MULTILINE)

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

        # Get round, if present
        order_round = USER_SPECIFIED_ROUNDS.get(message.author.id) or ""

        # Create fancy Discord embed
        title = "Order from %s" % affiliation
        if order_round:
            title = "*[Round %s]* " % order_round + title

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


if __name__ == "__main__":
    import logging
    import datetime

    logging.basicConfig(filename="aeldrum-ordersbot.log", level=logging.DEBUG)

    # Environment variables needed
    DISCORD_TOKEN = os.getenv("TOKEN")
    ORDERS_CHANNEL_ID = os.getenv("ORDERS_CHANNEL_ID")
    AELDRUM_SERVER_ID = os.getenv("AELDRUM_SERVER_ID")
    _required = (DISCORD_TOKEN, ORDERS_CHANNEL_ID, AELDRUM_SERVER_ID)

    # Configurable prefixes
    CMD_PREFIX = "!sendorder"
    ROUND_PREFIX = "!round"

    # Holding for !round commands
    USER_SPECIFIED_ROUNDS = {}

    # All env vars must be present
    if not all(_required):
        print("Please specify TOKEN, AELDRUM_SERVER_ID, and ORDERS_CHANNEL_ID")
    else:
        print("Started bot at %s" % datetime.datetime.now())
        client.run(DISCORD_TOKEN)
