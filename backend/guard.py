"""Hallucination backstop.

The system prompt already forbids inventing providers, but a prompt alone is
not a guarantee. This module re-checks the final answer: if the reply mentions
a doctor or hospital name that does not exist in the mock database, the reply is
replaced with a safe message and the unverified names are reported.

This is the last line of defence *behind* tool calling, not a replacement for
it.
"""

from __future__ import annotations

import re

from tools.search_providers import ProviderRepository

# --- patterns that look like a provider mention --------------------------
# Character classes allow any non-space character so that names written with
# a non-breaking hyphen ("Al-Noor Demo Hospital") still match.
_NAME_WORD = r"[A-Z][^\s,.;:!?()\[\]\"“”']*"
_LATIN_DOCTOR = re.compile(rf"Dr\.\s+{_NAME_WORD}(?:\s+{_NAME_WORD}){{0,2}}")
# The lookbehind stops Arabic words such as "شديد." from matching "د.".
_ARABIC_DOCTOR = re.compile(
    r"(?<![\w\u0600-\u06FF])د\.\s*[\w\u0600-\u06FF]{3,}(?:\s+[\w\u0600-\u06FF]+){0,2}"
)
_LATIN_FACILITY = re.compile(
    rf"(?:{_NAME_WORD}\s+){{1,4}}(?:Hospital|Clinic|Center|Centre)"
)
_ARABIC_FACILITY = re.compile(r"(مستشفى|مركز)\s+([\w\u0600-\u06FF]+)")

# Words that describe a facility instead of naming it ("the nearest hospital").
_GENERIC_NAME_WORDS = {
    "أقرب",
    "قريب",
    "الجديد",
    "الكبير",
    "الصغير",
    "الخاص",
    "العام",
    "الطارئ",
    "التدريب",
    "طبي",
    "الطبي",
    # Arabic function words: "المستشفى إذا ..." must not look like a name.
    "إذا",
    "إن",
    "أن",
    "و",
    "أو",
    "ثم",
    "لكن",
    "حيث",
    "هذا",
    "هذه",
    "الذي",
    "التي",
    "nearest",
    "near",
    "local",
}


def _norm(text: str) -> str:
    text = re.sub(r"^(?:dr|د)\s*\.?\s+", "", text.lower(), flags=re.UNICODE)
    text = re.sub(r"[^\w\u0600-\u06FF]+", " ", text)
    words = [word for word in text.split() if word not in _GENERIC_NAME_WORDS]
    return " ".join(words).strip()


def _candidates(reply: str) -> list[str]:
    candidates = _LATIN_DOCTOR.findall(reply)
    candidates += _ARABIC_DOCTOR.findall(reply)
    candidates += _LATIN_FACILITY.findall(reply)
    # Arabic facility names follow the keyword: "مستشفى النور" / "مركز الخليج".
    for match in _ARABIC_FACILITY.finditer(reply):
        keyword, name_word = match.group(1), match.group(2)
        if len(name_word) >= 3 and name_word not in _GENERIC_NAME_WORDS:
            candidates.append(f"{keyword} {name_word}")
    return candidates


def find_unverified_names(reply: str, repo: ProviderRepository) -> list[str]:
    """Return provider-looking names in `reply` that are not in the mock data."""
    known = [_norm(name) for name in repo.known_names()]
    unknown: list[str] = []
    for mention in _candidates(reply):
        candidate = _norm(mention)
        if not candidate:
            continue
        if any(candidate in name or name in candidate for name in known):
            continue
        if mention.strip() not in unknown:
            unknown.append(mention.strip())
    return unknown


FALLBACK_EN = (
    "I'm sorry, but I can't confirm a doctor or hospital that isn't in the "
    "available demo provider data, so I won't recommend one. Please ask me to "
    "search the verified demo providers, or contact your local health authority "
    "for a real referral."
)

FALLBACK_AR = (
    "عذرًا، لا أستطيع تأكيد طبيب أو مستشفى غير موجود في بيانات مزوّدي الخدمة "
    "التوضيحية المتاحة، لذلك لن أقترحه. يمكنك أن تطلب مني البحث في قائمة مزوّدي "
    "الخدمة الموثّقين، أو التواصل مع الجهة الصحية المحلية للحصول على إحالة حقيقية."
)


def enforce_grounding(reply: str, repo: ProviderRepository, language: str) -> tuple[str, list[str]]:
    """Return (safe_reply, unverified_names)."""
    unverified = find_unverified_names(reply, repo)
    if not unverified:
        return reply, []
    return (FALLBACK_AR if language == "ar" else FALLBACK_EN), unverified