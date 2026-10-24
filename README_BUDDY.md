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
- Optional: `GEMINI_MODEL` (default `gemini-2.5-flash-lite`). If the logs say the model isn't found,
  pick a Flash or Flash-Lite model name from the model list in AI Studio.
- Optional: `MAX_MSGS_PER_DAY` (default 60 per person). Free-tier limits are low, so a lower number is fine.
- If you later get an Anthropic key, add `ANTHROPIC_API_KEY` instead and remove the Gemini one.

To switch the buddy off, set `BUDDY_ENABLED` to `0`.

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

## 6. Review what people share
Open `https://YOUR-ADDRESS/submissions?key=YOUR_REPORT_KEY`. It lists shared reels with the AI's
category guess. A human should watch and approve before adding any to `library.json`.
Shared reels are NEVER sent to other people automatically.

## Limits of this first version
- Render's free plan erases saved data (what people like, which reels they've seen,
  the submissions list) whenever the server restarts. `library.json` is safe because it lives in GitHub.
- It handles one message at a time, which is fine for a few testers, not for hundreds.
- Only accounts with a role on your Meta app can message it until the app passes Meta's review.
- It can't verify anyone's age. The bot is told to stop if someone says they are under 18.
- Free-tier Gemini limits are small. If many people message at once, some replies will fail with a
  "brain glitched" message.
- Replies are written by an AI and can be wrong or awkward. Read the chats of your testers (with
  their permission) before inviting more people.
