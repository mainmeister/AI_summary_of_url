"""Content sanitization and filtering layer.

This module handles:
1. Cleaning web content extracted by the scraper before it is sent to the AI,
   neutralizing hidden-text smuggling and indirect prompt-injection payloads
   while preserving legitimate article text.
2. Filtering AI-generated output using ``texthumanize`` before presenting or
   dispatching it to downstream consumers.

Design goals:
- Deterministic, dependency-free HTML/Unicode cleaning (always available).
- Optional ``pytector`` injection-phrase cleaning, lazily imported and wrapped
  in try/except so a missing / incompatible package degrades gracefully.
- AI output humanization and filtering via ``texthumanize`` with clean-and-continue
  fallback behavior.
- Filtering must never raise into the caller; on failure it falls back to safe defaults.
"""

import logging
import re

from bs4 import Comment

logger = logging.getLogger(__name__)

# Invisible / smuggling Unicode code points that carry no legitimate visible
# meaning in article text but can be used to hide instructions from humans
# while remaining readable to the model.
_ZERO_WIDTH = frozenset({0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF})

# Inline-style signatures that visually hide an element from human readers.
_HIDDEN_STYLE_RE = re.compile(
    r"(display\s*:\s*none)"
    r"|(visibility\s*:\s*hidden)"
    r"|(opacity\s*:\s*0(?:\.0+)?\b)",
    re.IGNORECASE,
)


def strip_hidden_html(node, enabled: bool = True) -> None:
    """Remove visually-hidden content and HTML comments from a soup ``node``.

    Operates in-place on a BeautifulSoup element. Decomposes:
    - HTML comments (which the browser never renders but scrapers pick up);
    - elements carrying the ``hidden`` attribute;
    - elements whose inline ``style`` matches a hidden signature
      (``display:none``, ``visibility:hidden``, ``opacity:0``).

    Never raises: any unexpected error is logged and swallowed so scraping can
    continue on the un-stripped node.
    """
    if node is None or not enabled:
        return
    try:
        removed = 0

        # 1) HTML comments.
        for comment in node.find_all(string=lambda s: isinstance(s, Comment)):
            comment.extract()
            removed += 1

        # 2) Elements explicitly marked hidden or aria-hidden.
        for element in node.find_all(attrs={"hidden": True}):
            element.decompose()
            removed += 1
        for element in node.find_all(attrs={"aria-hidden": lambda v: bool(v) and str(v).lower() in ("true", "1")}):
            element.decompose()
            removed += 1

        # 3) Elements hidden via inline style.
        def _hidden_style(value: object) -> bool:
            return bool(value) and bool(_HIDDEN_STYLE_RE.search(str(value)))

        for element in node.find_all(style=_hidden_style):
            element.decompose()
            removed += 1

        if removed:
            logger.warning(
                "strip_hidden_html removed %d hidden/comment node(s).", removed
            )
    except Exception:
        logger.warning("strip_hidden_html failed; leaving node unmodified.", exc_info=True)


def strip_invisible_unicode(text: str, enabled: bool = True) -> str:
    """Remove invisible Unicode smuggling characters from ``text``.

    Strips the Unicode tag block (``U+E0000``-``U+E007F``), zero-width
    characters (ZWSP/ZWNJ/ZWJ/word-joiner/BOM) and bidirectional override
    controls (``U+202A``-``U+202E``). Visible characters are preserved.
    """
    if not text or not enabled:
        return text
    cleaned = "".join(
        c
        for c in text
        if not (0xE0000 <= ord(c) <= 0xE007F)
        and ord(c) not in _ZERO_WIDTH
        and not (0x202A <= ord(c) <= 0x202E)
    )
    if len(cleaned) != len(text):
        logger.warning(
            "strip_invisible_unicode removed %d invisible character(s).",
            len(text) - len(cleaned),
        )
    return cleaned


def strip_markdown(text: str) -> str:
    """Removes common Markdown formatting characters from the text."""
    if not text:
        return text
    text = re.sub(r'(\*\*|__)(.*?)\1', r'\2', text)
    text = re.sub(r'(\*|_)(.*?)\1', r'\2', text)
    text = text.replace('**', '').replace('__', '').replace('*', '').replace('_', '')
    text = text.replace('`', '')
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
    return text.strip()


def smart_truncate(text: str, limit: int) -> str:
    """Consistently truncates text to the last full sentence within the character limit."""
    if not text or limit <= 0:
        return text
    text = strip_markdown(text)
    if len(text) <= limit:
        return text

    snippet = text[:limit]
    # Find the last sentence-ending punctuation (. ! ?) optionally followed by closing quotes or parentheses
    matches = list(re.finditer(r'[.!?]["\'”’\)\]]?(?=\s|$)', snippet))
    threshold = int(limit * 0.6)

    if matches and matches[-1].end() > threshold:
        return snippet[:matches[-1].end()].strip()
    else:
        return snippet[:max(0, limit - 3)].rstrip() + "..."


def _pytector_sanitize(text: str) -> str:
    """Run ``pytector``'s input-sanitization pipeline if available.

    Lazily imported and fully guarded: a missing or Python-incompatible
    package (or any runtime error) simply returns the input unchanged.
    """
    try:
        from pytector import sanitize_prompt  # type: ignore
    except Exception:
        try:
            from pytector.sanitizer import sanitize_prompt  # type: ignore
        except Exception:
            logger.debug("pytector not available; skipping injection cleaning.")
            return text
    try:
        return sanitize_prompt(text)
    except Exception:
        logger.warning("pytector sanitization failed; using unmodified text.", exc_info=True)
        return text


def sanitize_text(text: str, strip_unicode: bool = True, use_pytector: bool = True) -> str:
    """Clean extracted text before it is sent to the AI.

    Pipeline: strip invisible Unicode -> pytector injection cleaning (best
    effort) -> whitespace normalization. Logs a warning when the sanitized
    text differs from the input. Never raises.
    """
    if not text:
        return text
    try:
        original = text
        text = strip_invisible_unicode(text, enabled=strip_unicode)
        if use_pytector:
            text = _pytector_sanitize(text)
        # Normalize whitespace (collapse runs, trim edges).
        text = re.sub(r"[ \t\f\v]+", " ", text)
        text = re.sub(r"\s*\n\s*", "\n", text)
        text = text.strip()
        if text != original:
            logger.warning("sanitize_text modified the extracted content.")
        return text
    except Exception:
        logger.warning("sanitize_text failed; returning original text.", exc_info=True)
        return text


def filter_ai_output(text: str, limit: int | None = None) -> str:
    """Filter and humanize AI-generated output using texthumanize.

    Cleans AI phrasing artifacts, normalizes typography, and ensures natural
    flow while preserving technical content and substance. When ``limit`` is
    provided, ensures the returned text is truncated to stay within the character
    limit. Lazily imported and guarded so that errors gracefully fall back to the
    original text (smart-truncated if a limit was set).
    Never raises.
    """
    if not text:
        return text
    try:
        import texthumanize
        result = texthumanize.humanize(text)
        if hasattr(result, "text") and result.text:
            output = result.text
        else:
            output = str(result)
        if limit is not None and limit > 0:
            output = smart_truncate(output, limit)
        return output
    except Exception:
        logger.warning("filter_ai_output failed; returning original AI output.", exc_info=True)
        if limit is not None and limit > 0:
            return smart_truncate(text, limit)
        return text
