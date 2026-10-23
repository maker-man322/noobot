# Reel test: can the bot get the actual video?

This small server answers one question: when someone shares a reel to your bot,
does the link Meta sends let us download the real video?

It only logs and tests. It does not summarize anything yet.

Menus on Meta's and your host's websites change often. If a button has a different
name than below, look for the closest one, or send me a screenshot.

## Part A: Put the server online (about 20 minutes)

You need a public web address that Meta can send messages to.

1. Make a free GitHub account, create a new repository, and upload `app.py` and
   `requirements.txt` (the "Add file > Upload files" button works).
2. Make an account on Render (render.com) and create a new **Web Service** from that repository.
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app --workers 1 --threads 4 --timeout 120`
3. In the service's **Environment** settings, add these (you invent the first and third):
   - `VERIFY_TOKEN` = any random phrase, for example `bluemango-4821`
   - `REPORT_KEY` = another random phrase (keeps your results private)
   - `APP_SECRET` = leave empty for now; fill in at step B3
4. When it's live, Render gives you an address like `https://something.onrender.com`.
   Opening it should show "Reel test server is running."

Free hosting may put the server to sleep when idle and may erase saved files when it
restarts. For this short test that's fine. Check results soon after sharing the reels,
and also copy the `/report` output somewhere safe.

## Part B: Connect it to Meta (about 30 minutes)

1. Go to developers.facebook.com, log in, and **Create App** (Business type).
2. Add the **Instagram** product. Choose **API setup with Instagram login**.
3. In the app's **Settings > Basic**, copy the **App Secret** and paste it into Render
   as `APP_SECRET`.
4. Under **API setup with Instagram login**, add the `noobody.bot` account and generate
   an access token. Keep it private.
5. Under **Configure webhooks**:
   - Callback URL: `https://YOUR-ADDRESS.onrender.com/webhook`
   - Verify token: the same `VERIFY_TOKEN` phrase
   - Subscribe to the **messages** field
6. Subscribe the account to the webhook. This is a separate step from step 5. The dashboard
   may have a toggle for it; otherwise your developer or I can give you the exact command.
7. Under **App roles**, add your normal Instagram account as an Instagram tester and accept
   the invite inside Instagram. Until the app passes Meta review, only accounts with a
   role on the app can message it.

## Part C: Run the test

1. From your normal account, share 5 different reels to `noobody.bot`:
   long caption, someone talking, text-and-music only, very short, 60+ seconds.
2. Open `https://YOUR-ADDRESS.onrender.com/report?key=YOUR_REPORT_KEY`.
3. Look at each entry:
   - `attachment_type`: should say `ig_reel`.
   - `attachment_payload`: the title, url and id Meta sent.
   - `downloads` > `status`: 200 means the link answered.
   - `downloads` > `looks_like_video`: **true** is the answer you want.
   - `saved_file`: the downloaded video. Get it at `/videos/FILENAME?key=YOUR_REPORT_KEY`
     and play it. Check that it has sound.
4. About 1 hour later, and again after 24 hours, open `/recheck?key=YOUR_REPORT_KEY`.
   This re-tests every saved link to see if it expires.

## How to read the result

- `looks_like_video: true` and the file plays with audio: the official route works.
- `status` is 200 but `looks_like_video` is false, or the status is 403/404:
  the link isn't a usable video. Users would need to send the video file themselves.
- Works now but fails on recheck: the link expires, so the real product must
  download the video the moment the message arrives.
- Nothing appears in the report at all: the webhook isn't connected right
  (check Part B steps 5 to 7, and the logs in Render).

Never share your access token, app secret, or report key.
