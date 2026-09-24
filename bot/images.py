import io
from typing import Optional

import aiohttp
from PIL import Image, ImageEnhance, ImageFilter

BANNER_SIZE = (1600, 640) 


async def _download(session: aiohttp.ClientSession, url: str) -> Optional[Image.Image]:
    try:
        async with session.get(url) as resp:
            resp.raise_for_status()
            raw = await resp.read()
        return Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        return None


def _cover_crop(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    tw, th = size
    scale = max(tw / img.width, th / img.height)
    resized = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left = (resized.width - tw) // 2
    top = (resized.height - th) // 2
    return resized.crop((left, top, left + tw, top + th))


def _make_banner(art: Image.Image) -> Image.Image:
    """Wide art is cropped straight to the banner ratio. Portrait/square art
    (box art, profile pictures) is centered over a blurred, darkened copy of
    itself so it fills the banner without looking stretched."""
    w, h = BANNER_SIZE
    if art.width / art.height >= 1.5:
        return _cover_crop(art, BANNER_SIZE)

    bg = _cover_crop(art, BANNER_SIZE).filter(ImageFilter.GaussianBlur(30))
    bg = ImageEnhance.Brightness(bg).enhance(0.45)
    fg_h = int(h * 0.88)
    fg = art.resize((round(art.width * fg_h / art.height), fg_h), Image.LANCZOS)
    bg.paste(fg, ((w - fg.width) // 2, (h - fg_h) // 2))
    return bg


async def build_cover(
    session: aiohttp.ClientSession,
    box_art_url: Optional[str],
    offline_banner_url: Optional[str],
    profile_image_url: Optional[str],
) -> Optional[bytes]:
    art = None
    for url in (box_art_url, offline_banner_url, profile_image_url):
        if url:
            art = await _download(session, url)
            if art:
                break
    if art is None:
        return None

    banner = _make_banner(art)
    buf = io.BytesIO()
    banner.save(buf, format="JPEG", quality=88)
    return buf.getvalue()
