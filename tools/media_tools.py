"""
tools/media_tools.py
====================

yt-dlp helper — YouTube audio CDN stream extraction.
"""

import yt_dlp


def get_audio_stream(query: str) -> tuple[str, str]:
    """
    Search YouTube for `query` and return (cdn_stream_url, title).

    Args:
        query: Search text (e.g. "lo-fi hip hop") or a direct YouTube URL.

    Returns:
        (cdn_url, title) — cdn_url is the direct audio stream URL.

    Raises:
        Exception: if yt-dlp cannot find or extract the video.
    """
    ydl_opts = {
        "format":         "bestaudio/best",
        "noplaylist":     True,
        "quiet":          True,
        "no_warnings":    True,
        "default_search": "ytsearch1",
        "extract_flat":   False,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)
        if "entries" in info and info["entries"]:
            info = info["entries"][0]
        return info["url"], info.get("title", query)
