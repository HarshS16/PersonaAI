"""X (Twitter) archive import from the user's own data export.

X has no free general-purpose API, so the supported path is the user's archive
(Settings → Download an archive of your data). The archive's data/tweets.js is a
JS assignment wrapping a JSON array; we strip the prefix and read each tweet's
text. Retweets are skipped. These feed search and writing-style analysis.
"""

from __future__ import annotations

import io
import json
import re
import zipfile

from app.core.errors import AppError

MAX_TWEETS = 300
_PREFIX = re.compile(r"^\s*window\.YTD\.tweets\.part\d+\s*=\s*", re.IGNORECASE)


def _texts_from_tweets_js(raw: str) -> list[str]:
    body = _PREFIX.sub("", raw).strip()
    try:
        entries = json.loads(body)
    except json.JSONDecodeError as exc:
        raise AppError("Could not parse tweets.js", code="bad_x_archive") from exc

    texts: list[str] = []
    for entry in entries:
        tweet = entry.get("tweet", entry) if isinstance(entry, dict) else {}
        text = (tweet.get("full_text") or tweet.get("text") or "").strip()
        if text and not text.startswith("RT @"):
            texts.append(text)
    return texts


def parse_x_archive(data: bytes, filename: str) -> list[str]:
    # Accept either the whole ZIP or just the tweets.js file.
    if filename.lower().endswith(".js") or data[:20].lstrip().lower().startswith(b"window.ytd"):
        texts = _texts_from_tweets_js(data.decode("utf-8", errors="replace"))
    else:
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as exc:
            raise AppError("Not a valid X archive ZIP", code="bad_zip") from exc
        name = next(
            (n for n in zf.namelist() if n.lower().endswith("tweets.js")
             or n.lower().endswith("tweet.js")),
            None,
        )
        if name is None:
            raise AppError("No tweets.js found in the archive", code="no_tweets")
        texts = _texts_from_tweets_js(zf.read(name).decode("utf-8", errors="replace"))

    if not texts:
        raise AppError("No tweets found in the archive", code="empty_x_archive")
    return texts[:MAX_TWEETS]
