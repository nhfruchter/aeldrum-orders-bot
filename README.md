# aeldrum-orders-bot

Aeldrum orders discord bot.

Thanks Bruce for many contributions.

**Setting up the Bot**

* Create a new VM on your cloud provider of choice (minimal compute resources needed)
* Create a new bot [on Discord](https://discord.com/developers/applications) to get the client ID and secret
* Obtain your server's ID and the channel ID you want to mirror orders into

**If you want to duplicate orders to a sheet**: 

* SSH into your VM 
* Edit `ordersbot.py` and set the `LOG_TO_SHEET` variable to the ID of a Google Sheet you have edit access to.
* Run `sheetslogger.py` from the command line and open the URL it spits out to generate an OAuth token for the bot
* Use `wget`, `curl`, or a browser to query the localhost URL that Google tries to redirect you to after authorization

**Running the bot**

* SSH into your VM 
* Set `DISCORD_TOKEN, ORDERS_CHANNEL_ID, AELDRUM_SERVER_ID` as environment variables and run ordersbot.py in a persistent shell (e.g. `screen`).
