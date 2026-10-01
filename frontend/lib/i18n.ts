/** Tiny i18n table - UI labels only. The AI replies in the patient's language. */

export type Language = "en" | "ar";

export const DIRECTION: Record<Language, "ltr" | "rtl"> = {
  en: "ltr",
  ar: "rtl",
};

type Labels = {
  title: string;
  subtitle: string;
  inputPlaceholder: string;
  send: string;
  sending: string;
  you: string;
  assistant: string;
  disclaimer: string;
  emptyState: string;
  suggestion: string;
  verifiedProviders: string;
  emergencyBanner: string;
  languageLabel: string;
  toolsUsed: string;
};

export const LABELS: Record<Language, Labels> = {
  en: {
    title: "HealTrip AI Patient Decision Assistant",
    subtitle: "Decision support for your next step in care.",
    inputPlaceholder: "Describe your situation, e.g. “I have chest pain and I'm not sure what to do.”",
    send: "Send",
    sending: "Thinking…",
    you: "You",
    assistant: "HealTrip Assistant",
    disclaimer:
      "Demo prototype. HealTrip provides general decision support only and does not diagnose or replace a clinician or emergency services. All doctors and hospitals shown come from fictional demo data.",
    emptyState: "Ask about your symptoms or request a verified demo doctor or hospital.",
    suggestion: "Try:",
    verifiedProviders: "Verified demo providers",
    emergencyBanner: "If this may be an emergency, contact your local emergency number now.",
    languageLabel: "Language",
    toolsUsed: "tool calls",
  },
  ar: {
    title: "مساعد HealTrip الذكي لقرارات المريض",
    subtitle: "دعم للقرار حول خطوتك التالية في الرعاية الصحية.",
    inputPlaceholder: "صف حالتك، مثال: «عندي ألم في الصدر ولا أعرف ماذا أفعل».",
    send: "إرسال",
    sending: "جارٍ التفكير…",
    you: "أنت",
    assistant: "مساعد HealTrip",
    disclaimer:
      "نموذج تجريبي. يقدّم HealTrip دعمًا عامًا للقرار فقط، ولا يقدّم تشخيصًا ولا يحل محل الطبيب أو خدمات الطوارئ. جميع الأطباء والمستشفيات المعروضة بيانات توضيحية خيالية.",
    emptyState: "اسأل عن أعراضك أو اطلب طبيبًا أو مستشفى موثّقًا من البيانات التوضيحية.",
    suggestion: "جرّب:",
    verifiedProviders: "مزودو خدمة موثّقون (بيانات توضيحية)",
    emergencyBanner: "إذا كانت الحالة طارئة، فاتصل برقم الطوارئ المحلي فوراً.",
    languageLabel: "اللغة",
    toolsUsed: "استدعاءات الأدوات",
  },
};

export const SUGGESTIONS: Record<Language, string[]> = {
  en: [
    "I have chest pain and I'm not sure whether to see a cardiologist, go to the ER, or get a second opinion.",
    "I need a cardiologist in Riyadh.",
    "Which demo hospitals have emergency service?",
  ],
  ar: [
    "عندي ألم في الصدر ولا أعرف هل أذهب للطبيب أم للطوارئ.",
    "أريد طبيب قلب في الرياض.",
    "ما هي المستشفيات التوضيحية التي توفر خدمة الطوارئ؟",
  ],
};