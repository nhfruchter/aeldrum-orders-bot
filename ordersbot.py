import discord
import os
import re

client = discord.Client()

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

  # Identify the channel that orders will be sent to
  order_channel_id = os.getenv('ORDERS_CHANNEL_ID')
  order_channel = client.get_channel(int(order_channel_id))

  # Error message if order channel is not set
  if (order_channel == None):
    await message.channel.send('Could not find channel ' + order_channel_id)
    logging.warning("Unable to find channnel " + order_channel_id)

  # Only respond to messages starting with the command flag
  CMD_RE = r"^" + CMD_PREFIX + r"(\[[^\]]*])? (.+)"
  parsed = re.findall(CMD_RE, message.content, re.IGNORECASE + re.MULTILINE)

  if len(parsed):  
    # args[0] = blank if no alt affiliation, args[1] = message
    args = parsed[0]
    content = args[1].strip()
        
    # Attribute the message to the user's nickname, not the username
    author = getattr(message.author, 'nick', str(message.author))
    
    # Grab the files, if any
    files = await files_from_attachments(message.attachments)
    logging.debug("%s, %s, files: %s", author, content, len(files))
    
    # Affiliation/title for embed
    affiliation = args[0].replace("[", "").replace("]", "") if args[0] else message.author.top_role

    # Create fancy Discord embed
    out_message = discord.Embed(
      title="Order from %s" % affiliation,
      description=content
    )
    
    # Set embed author to sender
    out_message.set_author(
      name=message.author.display_name,
      icon_url=message.author.avatar_url
    )

    await order_channel.send(embed=out_message, files=files)
    await message.add_reaction("👍")

if __name__ == '__main__':
  import logging
  logging.basicConfig(filename='aeldrum-ordersbot.log', level=logging.DEBUG)
  
  DISCORD_TOKEN = os.getenv('TOKEN')  
  CMD_PREFIX = '!sendorder'
  
  client.run(DISCORD_TOKEN)