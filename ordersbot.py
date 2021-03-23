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
  server = client.get_guild(int(os.getenv("AELDRUM_SERVER_ID")))
  member = server.get_member(member_id)
  return member.top_role


@client.event
async def on_message(message):
    """Handle each incoming message."""

    # Ignore self
    if message.author == client.user:
        return

    # Accept requests only from valid sources
    if message.channel.type != discord.ChannelType.private and message.guild.id != int(os.getenv("AELDRUM_SERVER_ID")):
      return

    # Identify the channel that orders will be sent to
    order_channel_id = os.getenv("ORDERS_CHANNEL_ID")
    order_channel = client.get_channel(int(order_channel_id))

    # Error message if order channel is not set
    if order_channel == None:
        await message.channel.send("Could not find channel " + order_channel_id)
        logging.warning("Unable to find channnel " + order_channel_id)

    # Only respond to messages starting with the command flag
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
            else getattr(message.author, 'top_role', await get_default_role(message.author.id))
        )

        # Create fancy Discord embed
        out_message = discord.Embed(
            title="Order from %s" % affiliation, description=content
        )

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

    logging.basicConfig(filename="aeldrum-ordersbot.log", level=logging.DEBUG)

    DISCORD_TOKEN = os.getenv("TOKEN")
    CMD_PREFIX = "!sendorder"

    client.run(DISCORD_TOKEN)
