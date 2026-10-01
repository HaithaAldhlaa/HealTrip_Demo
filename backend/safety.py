"""Very small, conservative medical-safety layer.

This is NOT a triage engine or a diagnosis engine. It only does two things:

1. Detects a handful of obvious red-flag phrases (English + Arabic) so the
   Agent is forced to prioritise emergency care instead of recommending a
   routine appointment.
2. Detects that a medical symptom was mentioned at all, so the Agent asks a
   clarifying question before recommending a provider.

Both lists are intentionally short and readable.
"""

from __future__ import annotations

import re

EMERGENCY_PATTERNS: tuple[str, ...] = (
    r"severe chest pain|crushing chest pain|chest pain (?:that )?(?:radiat|spread)",
    r"cannot breathe|can't breathe|not breathing|difficulty breathing|trouble breathing|shortness of breath",
    r"choking|throat (?:is )?closing|anaphyla",
    r"fainted|fainting|passed out|unconscious|loss of consciousness|black(ed)? out",
    r"severe bleeding|bleeding heavily|heavy bleeding|won'?t stop bleeding",
    r"stroke|face (?:is )?drooping|slurred speech|cannot speak",
    r"seizure|convulsion|fitting",
    r"severe burn|severe allergic reaction",
    r"severe abdominal pain",
    r"ألم شديد في الصدر|ألم شديد بالصدر",
    r"لا أستطيع التنفس|صعوبة في التنفس|ضيق في التنفس|لا يمكنني التنفس",
    r"اختناق|تضخم الحلق|حساسية شديدة",
    r"فقدان الوعي|أفقد وعيي|اغماء|إغماء",
    r"نزيف شديد|نزيف غزير|نزيف لا يتوقف",
    r"جلطة|شلل مفاجئ|شلل نصفي|تردد في الكلام|لا يستطيع الكلام",
    r"نوبة تشنجية|تشنجات",
)

SYMPTOM_PATTERNS: tuple[str, ...] = (
    r"pain|ache|fever|dizzy|nausea|rash|cough|bleeding|swelling|shortness of breath|unwell|sick",
    r"ألم|وجع|حرارة|دوار|غثيان|طفح|سعال|نزيف|تورم|ضيق|تعب|مريض",
)

_EMERGENCY_RE = re.compile("|".join(EMERGENCY_PATTERNS), re.IGNORECASE)
_SYMPTOM_RE = re.compile("|".join(SYMPTOM_PATTERNS), re.IGNORECASE)

ARABIC_RE = re.compile(r"[\u0600-\u06FF]")


def detect_language(text: str, default: str = "en") -> str:
    return "ar" if ARABIC_RE.search(text) else default


def is_emergency(text: str) -> bool:
    return bool(_EMERGENCY_RE.search(text))


def mentions_symptom(text: str) -> bool:
    return bool(_SYMPTOM_RE.search(text))


URGENT_DIRECTIVE_EN = (
    "URGENCY: the patient described a possible emergency. Your FIRST sentence must "
    "tell them to seek immediate in-person medical care now (nearest emergency "
    "department, or their local emergency number - never assume a country-specific "
    "number such as 911). Do NOT recommend a routine specialty appointment as the "
    "primary next step, do NOT reassure them, and do NOT delay with questions. You "
    "may then add: one brief clarifying question, and if the patient asks for a "
    "facility, use the tools to list hospitals that have emergency_available = true."
)

URGENT_DIRECTIVE_AR = (
    "استعجال: وصف المريض حالة طارئة محتملة. يجب أن تكون أول جملة تنصحه بتلقي "
    "رعاية طبية شخصية فورًا (أقرب قسم طوارئ أو رقم الطوارئ المحلي). لا تقترح موعد "
    "تخصصي روتيني كخطوة أولى، ولا تطمئنه، ولا تؤخر الرد بأسئلة. يمكن بعدها طرح "
    "سؤال توضيحي قصير واحد، وعند طلبه منشأة استخدم الأدوات لعرض المستشفيات "
    "المتاحة فيها خدمة الطوارئ."
)

CLARIFY_DIRECTIVE_EN = (
    "CLARIFICATION: the patient reports a symptom. Ask ONE short, relevant "
    "clarifying question (for example: when did it start, how severe is it, is it "
    "worsening, any other symptoms) before recommending a provider or a facility. "
    "Do not state or imply a diagnosis."
)

CLARIFY_DIRECTIVE_AR = (
    "توضيح: يذكر المريض أعراضًا. اطرح سؤال توضيحيًا قصيرًا واحدًا قبل أن تقترح "
    "طبيبًا أو منشأة (مثلًا: متى بدأت الأعراض؟ ما شدتها؟ هل تتفاقم؟ هل هناك أعراض "
    "أخرى؟). لا تذكر أو توحي بأي تشخيص."
)