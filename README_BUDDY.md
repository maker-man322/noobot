# Reel buddy: setup

What it does: when someone messages `noobody.bot`, it replies like a casual AI buddy.
- Shared reel: reads the caption (it cannot see the video), files it for review, reacts,
  then sends one reel from `library.json` as a sentence plus a clean preview card.
- Text: short friendly reply; remembers what the person likes; sends a reel if asked.

## 1. Upload to GitHub (same repository as before)
Add these files and replace the old one: `buddy.py` (new), `library.json` (new), `app.py` (replace).
Commit, and wait for Render to show "Live".

## 2. Get a free Gemini API key
- Go to aistudio.google.com, sign in with your Google account, and use **Get API key** > **Create API key**.
- This key is separate from your Gemini Pro subscription. The subscription powers the Gemini app,
  while the API has its own free tier with rate limits. Google has said new AI Studio users may be
  asked to start on a prepaid plan, so if it asks for a payment, stop and tell me.
- On the free tier, Google may use what you send to improve its products. Only test with people who
  know their messages go to Google. Before inviting real users, move to a paid tier.
- Paste the key ONLY into Render. Never into a chat or a file.

## 3. Add these in Render > Environment
- `GEMINI_API_KEY` = your key
- `BUDDY_ENABLED` = `1`
- `IG_ACCESS_TOKEN` = must already be set (the token for noobody.bot)
- Optional: `GEMINI_MODEL` (default `gemini-3.5-flash-lite`). If the logs say the model isn't found,
  pick a Flash or Flash-Lite model name from the model list in AI Studio.
- Optional: `MAX_MSGS_PER_DAY` (default 60 per person). Free-tier limits are low, so a lower number is fine.
- If you later get an Anthropic key, add `ANTHROPIC_API_KEY` instead and remove the Gemini one.

To switch the buddy off, set `BUDDY_ENABLED` to `0`.

## 3b. Give the bot a permanent memory (Upstash, free)
Without this, the bot forgets everything whenever Render restarts the free server. That is why it
introduced itself again and again.
1. Go to upstash.com and sign up (free, no card).
2. Create a **Redis** database. Pick the region closest to your Render server.
3. On the database page, find the **REST API** section and copy `UPSTASH_REDIS_REST_URL` and
   `UPSTASH_REDIS_REST_TOKEN`.
4. Add both in Render > Environment with those exact names. Save and wait for "Live".
The free plan allows 500,000 commands a month and 256 MB, which is far more than a test needs.
If you skip this step, the bot still works but loses its memory on every restart.

## Optional settings
- `DEBOUNCE_SECONDS` (default 3): how long the bot waits for you to finish typing several messages
  before it answers them together.
- `GEMINI_MODEL`: if replies still feel flat, try a larger Flash model from AI Studio's model list.
  Bigger models write better but have lower free limits.

## 3c. Optional: let the bot message first, now and then
Instagram only lets a bot message someone within 24 hours of THEIR last message. So the bot can start a
conversation or send a reel during the day, but only to people who wrote to it recently.
1. In Render > Environment add `NUDGES_ENABLED` = `1`.
2. Use a free timer such as cron-job.org to open this address every 10 minutes (it also keeps the free
   Render server awake):
   `https://YOUR-ADDRESS/tick?key=YOUR_REPORT_KEY`
3. Built-in limits: only people who messaged in the last 22 hours, only between 10:00 and 21:30 India
   time, at most 2 per person per day (`NUDGES_PER_DAY`), never after two unanswered ones, never within 24
   hours of a crisis moment, and only a gentle message (no reel) within 12 hours of a low moment.
   Anyone can say "stop sending me stuff" and the bot stops. Change the hours with `NUDGE_START_HOUR`,
   `NUDGE_END_HOUR` and `TZ_OFFSET_MINUTES`.
Instagram watches for people who ignore or block bots, so keep this light.

## 4. Test
From your tester account, share a reel to `noobody.bot`. Expected: an intro line (first time only),
a reaction, then a sentence and a reel card. Then send a text like "send me something about science".

## 5. Fill the library
Edit `library.json` on GitHub. One entry per reel:

    {"id": "short-unique-name", "url": "https://www.instagram.com/reel/XXXX/",
     "category": "science", "tags": ["ocean"], "note": "one line saying what the reel is"}

The `note` is how the bot knows what the reel is, since it cannot watch it. Write it honestly.
Valid categories: sports, comedy, memes, animals, food, travel, fitness, fashion, business, finance,
tech, ai, science, space, education, news, music, movies_tv, gaming, health, cars, art_design,
relationships, conspiracies, local_india, other.
The two entries in the file are placeholders from your own tests. Replace them.

## 5b. Easier: keep the library in a Google Sheet
Editing GitHub for every reel is slow. A Google Sheet is faster and works from your phone.
1. Make a new Google Sheet and import `library_template.csv` (File > Import), or copy its columns:
   `url, category, tags, note, summary`.
2. Add one row per reel. `url` and `category` are required. `note` is one line saying what the reel is.
   `summary` is 2 to 3 sentences of what it actually says, so the bot can talk about it later.
3. Publish it: **File > Share > Publish to web**, choose the sheet tab and the **CSV** format,
   click Publish, and copy the link.
4. In Render > Environment add `LIBRARY_CSV_URL` = that link.
The bot re-reads the sheet every 5 minutes. If the sheet can't be read it keeps the last good copy, and
falls back to `library.json`. Anyone with the link can read the sheet, so only put public reels in it.

Why the notes matter: the bot cannot watch videos. Whatever you write in `note` and `summary` is
everything it knows about that reel, so write what the reel really says, not what you guess.

## Different styles for different people
Each person gets one of three styles:
- **direct**: short, to the point, no small talk, no emojis, quicker typing, at most 1 message-first per day.
- **buddy** (default): warm and chatty, asks follow-ups, brings up things they told it.
- **reels**: mostly content. Minimal chat, a new reel sent more often, one extra message-first per day.
How it picks: a person can ask ("keep it short", "just send me reels", "be more chatty", "go back to normal")
and the bot remembers. Otherwise, after about 6 messages, it guesses from behaviour: someone who mostly sends
reels and barely chats becomes "reels", and the AI can suggest "direct" or "buddy" from how they write.
An explicit request always wins over a guess. If someone is struggling, the bot drops the style and responds warmly.
Saying "forget me" resets the style too.

## What the bot remembers about each person
- Interests (a tally per category), reels already seen, the last 12 messages, and simple things they
  tell it ("supports RCB"). It is told not to keep sensitive things (health, religion, politics, money,
  phone numbers, addresses). That is an instruction to an AI, not a guarantee, so read some chats.
- A short note on how they text and what they enjoy (never feelings or health), used to feel more personal.
- Saying "forget me" wipes everything the bot holds about that person.
- With Upstash set up, memory survives restarts. Without it, everything is lost on restart.

## Seen and typing
The bot marks messages as seen, pauses briefly, shows the typing bubble for a time that grows with the
message length, then sends. The pauses are in the `say()` function in `buddy.py`.

## 5c. Collect the reels people share into your spreadsheet
The bot saves every reel people share (link, caption, the AI's category guess, and any note the person gave
in the next 30 minutes, such as "it's a cheap 30 day plan to learn python"). Nothing is sent to anyone until
you approve it.
1. In the same spreadsheet, add a new tab called `Submissions`. Do NOT publish this tab.
2. In cell A1 of that tab, paste:
   `=IMPORTDATA("https://YOUR-ADDRESS/submissions.csv?key=YOUR_REPORT_KEY")`
3. The tab fills with: url, category, tags, note, summary, status, id, caption. Google refreshes it
   from time to time, so new shares appear on their own.
4. Open each link, watch the reel, fix the category and note, and write the `summary`.
5. Copy the approved rows (paste as values only) into your published Library tab and change `status` to
   `approved`, or delete the status cell. Rows whose status is `pending`, `rejected`, `hold` or `no` are
   never sent to anyone.
Unsafe reels are left out of the list. The list never contains who shared a reel.

## 6. Review what people share
Open `https://YOUR-ADDRESS/submissions?key=YOUR_REPORT_KEY`. It lists shared reels with the AI's
category guess. A human should watch and approve before adding any to `library.json`.
Shared reels are NEVER sent to other people automatically.

## Limits of this first version
- Without Upstash, Render's free plan erases saved data whenever the server restarts.
  `library.json` is always safe because it lives in GitHub.
- It handles one message at a time, which is fine for a few testers, not for hundreds.
- Only accounts with a role on your Meta app can message it until the app passes Meta's review.
- It can't verify anyone's age. The bot is told to stop if someone says they are under 18.
- Free-tier Gemini limits are small. If many people message at once, some replies will fail with a
  "brain glitched" message.
- Replies are written by an AI and can be wrong or awkward. Read the chats of your testers (with
  their permission) before inviting more people.
