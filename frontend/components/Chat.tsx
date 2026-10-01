"use client";

import { useEffect, useRef, useState } from "react";

import ProviderCard from "@/components/ProviderCard";
import { sendChat, type Language, type Provider, type ToolTrace } from "@/lib/api";
import { DIRECTION, LABELS, SUGGESTIONS } from "@/lib/i18n";

type Message = {
  id: number;
  role: "user" | "assistant";
  content: string;
  urgent?: boolean;
  grounded?: boolean;
  providers?: Provider[];
  toolsUsed?: ToolTrace[];
};

const HISTORY_WINDOW = 8;

const CARD_LABELS = {
  en: {
    doctor: "Doctor",
    hospital: "Hospital",
    specialties: "Specialties",
    at: "Works at",
    emergency: "Emergency service available",
    noEmergency: "No emergency service listed",
    languages: "Languages",
    address: "Address",
  },
  ar: {
    doctor: "طبيب",
    hospital: "مستشفى",
    specialties: "التخصصات",
    at: "يعمل في",
    emergency: "خدمة الطوارئ متوفرة",
    noEmergency: "لا توجد خدمة طوارئ مدرجة",
    languages: "اللغات",
    address: "العنوان",
  },
} as const;

export default function Chat() {
  const [language, setLanguage] = useState<Language>("en");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [urgent, setUrgent] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const t = LABELS[language];

  // RTL for Arabic, LTR for English.
  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.dir = DIRECTION[language];
  }, [language]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pending]);

  async function handleSend(text: string) {
    const message = text.trim();
    if (!message || pending) return;

    setError(null);
    setPending(true);
    setInput("");

    const history = messages
      .slice(-HISTORY_WINDOW)
      .map(({ role, content }) => ({ role, content }));
    const userMessage: Message = { id: Date.now(), role: "user", content: message };
    setMessages((current) => [...current, userMessage]);

    try {
      const data = await sendChat(message, language, history);
      setMessages((current) => [
        ...current,
        {
          id: Date.now() + 1,
          role: "assistant",
          content: data.reply,
          urgent: data.urgent,
          grounded: data.grounded,
          providers: data.providers,
          toolsUsed: data.tools_used,
        },
      ]);
      if (data.urgent) setUrgent(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t.disclaimer);
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="app">
      <header className="header">
        <div>
          <h1>{t.title}</h1>
          <p>{t.subtitle}</p>
        </div>
        <div className="lang-switch" role="group" aria-label={t.languageLabel}>
          {(["en", "ar"] as const).map((code) => (
            <button
              key={code}
              type="button"
              aria-pressed={language === code}
              onClick={() => setLanguage(code)}
            >
              {code === "en" ? "English" : "العربية"}
            </button>
          ))}
        </div>
      </header>

      {urgent ? <div className="emergency-banner">{t.emergencyBanner}</div> : null}

      <section className="messages" aria-live="polite">
        {messages.length === 0 ? (
          <div className="empty-state">
            <div>{t.emptyState}</div>
            <div className="suggestions">
              <span>{t.suggestion}</span>
              {SUGGESTIONS[language].map((suggestion) => (
                <button key={suggestion} type="button" onClick={() => handleSend(suggestion)}>
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {messages.map((message) => (
          <div key={message.id} className={`bubble ${message.role}`}>
            <div className="bubble-meta">{message.role === "user" ? t.you : t.assistant}</div>
            <div>{message.content}</div>

            {message.role === "assistant" && message.providers && message.providers.length > 0 ? (
              <div className="providers">
                <div className="providers-title">{t.verifiedProviders}</div>
                {message.providers.map((provider) => (
                  <ProviderCard
                    key={`${provider.type}-${provider.id}`}
                    provider={provider}
                    labels={CARD_LABELS[language]}
                  />
                ))}
              </div>
            ) : null}

            {message.role === "assistant" && message.toolsUsed && message.toolsUsed.length > 0 ? (
              <div className="providers-title" style={{ marginTop: 6 }}>
                {message.toolsUsed.length} {t.toolsUsed}
              </div>
            ) : null}
          </div>
        ))}

        {pending ? <div className="bubble assistant">{t.sending}</div> : null}
        <div ref={bottomRef} />
      </section>

      {error ? (
        <div className="error" role="alert">
          <span>{error}</span>
          <button type="button" onClick={() => setError(null)} aria-label="Dismiss">
            ×
          </button>
        </div>
      ) : null}

      <form
        className="form"
        onSubmit={(event) => {
          event.preventDefault();
          void handleSend(input);
        }}
      >
        <textarea
          value={input}
          placeholder={t.inputPlaceholder}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void handleSend(input);
            }
          }}
        />
        <button type="submit" disabled={pending || input.trim().length === 0}>
          {pending ? t.sending : t.send}
        </button>
      </form>

      <footer className="disclaimer">{t.disclaimer}</footer>
    </main>
  );
}