# Twitch Schedule To Discord Events Bot

A Discord bot that mirrors any Twitch channel's schedule into a server's
scheduled events, with an automatically generated cover image per event.
The bot is run once by you and then usable by any number of streamers. They never
touch a token or a terminal.

## How it works

- Any server that runs `/schedule link <twitch_channel>` gets that channel's
  upcoming schedule synced into Discord scheduled events.
- A background task re-checks every linked server on a timer (default: every
  30 minutes) and creates any new segments, using each event's description
  to remember which Twitch segment it came from so re-syncing never creates
  duplicates.
- Optionally (on by default) it removes Discord events whose Twitch segment
  was cancelled.
- Optionally (on by default) it generates a cover image per event from the
  stream category's box art, falling back to the channel's offline banner
  or profile picture.

## 1. Create your Twitch app (you do this once)

1. Go to [dev.twitch.tv/console](https://dev.twitch.tv/console) -> **Register Your Application**.
2. OAuth Redirect URL can be `http://localhost` — it's unused for this flow.
3. Copy the **Client ID**, then generate and copy a **Client Secret**.

This app reads public schedules only, so streamers never authorize
anything on their end.

## 2. Create your Discord bot (you do this once)

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) -> **New Application**.
2. Under **Bot**, click **Reset Token** and copy it. Keep it secret.
3. Under **OAuth2 → URL Generator**, select scope `bot` and permissions
   `Manage Events` and `View Channels`. Use the generated URL as your
   invite link.
4. No privileged intents (message content, presence, members) are needed.

## 3. Run the bot

### Option A: Docker (recommended)

```bash
cp .env.example .env
# fill in .env with your values
docker compose up -d
```

### Option B: use Python in Venv

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# fill in .env with your values
cd bot
python main.py
```

Requires Python 3.11+.

### Hosting

Any always-on host works: a $5/mo VPS, Fly.io, Railway, or a Raspberry Pi.
Slash commands sync globally by default, which can take up to an hour to
appear in a new server the first time. Set `DEV_GUILD_ID` in `.env` to your
own test server's ID while developing so commands there update instantly.

## 4. How to use the bot

Use the invitation link in the "Bot Invitation Link" file.
When the bot appears in the list of server members, use this command in any text chat
to link your Twitch channel:

```
/schedule link twitch_channel:yourchannelname
```

The first sync runs immediately, and it keeps itself updated
from then on. Other commands:

- `/schedule status` — shows the linked channel, settings, and last sync time
- `/schedule sync` — forces an immediate re-sync
- `/schedule unlink` — stops syncing (existing events are left alone)

`/schedule link` also takes optional settings: `days_ahead` (default 30),
`cover_images` (default on), and `prune` (default on).

## Project layout

```
bot/
  main.py           entrypoint, background sync loop
  config.py         env var loading
  db.py             SQLite storage of per-guild settings
  twitch_api.py     Twitch Helix API client
  images.py         cover image generation
  sync.py           core sync logic (shared by loop + manual /schedule sync)
  cogs/
    schedule.py     slash commands
requirements.txt
Dockerfile
docker-compose.yml
.env.example
```

## Notes & limits

- Discord allows roughly 100 scheduled events per server.
- Discord requires bot verification once the bot is in 100+ servers.
- The bot's own Twitch app token is shared across all guilds. Since it's an app
  token, it's not tied to any streamer's account, since schedules are public.
- Guard `DISCORD_BOT_TOKEN` and `TWITCH_CLIENT_SECRET` — anyone with the
  Discord token controls the bot in every server it's in.
- `schedule_sync.db` (or `data/schedule_sync.db` under Docker) holds all
  linked servers' settings. Back it up if you care about not having to
  ask everyone to re-link.
