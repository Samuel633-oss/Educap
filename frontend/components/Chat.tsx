"use client";
import { useEffect, useRef, useState } from "react";
import { ArrowUp, BookOpen, Brain, ClipboardCheck, Compass, FlaskConical, Layers, Lightbulb, Search, Sparkles, Stethoscope, TrendingUp, TrendingDown, CalendarDays } from "lucide-react";
import Markdown from "./Markdown";
import Flashcards from "./Flashcards";
import { getMessages, streamChat } from "@/lib/api";
import type { ChatMessage, Student } from "@/lib/types";

const AGENTS: Record<string, { label: string; Icon: any; tone: string }> = {
  tutor: { label: "Tutor", Icon: BookOpen, tone: "bg-mist text-pine" },
  socratic: { label: "Socratic", Icon: Lightbulb, tone: "bg-cap/30 text-pine" },
  exam: { label: "Exam", Icon: ClipboardCheck, tone: "bg-pine text-paper" },
  assessment: { label: "Assessment", Icon: Brain, tone: "bg-berry/15 text-berry" },
  case: { label: "Case", Icon: Stethoscope, tone: "bg-moss text-paper" },
  revision: { label: "Revision", Icon: Compass, tone: "bg-cap/30 text-pine" },
  flashcards: { label: "Flashcards", Icon: Layers, tone: "bg-mist text-pine" },
  planner: { label: "Planner", Icon: CalendarDays, tone: "bg-mist text-pine" },
  research: { label: "Research", Icon: Search, tone: "bg-mist text-pine" },
  system: { label: "System", Icon: FlaskConical, tone: "bg-berry/15 text-berry" },
};
const SUGGESTIONS = ["Teach me photosynthesis", "Explain derivatives", "Quiz me on anatomy", "I don't understand recursion",
  "Give me a clinical case about heart failure", "What should I revise?"];

export default function Chat({ student, conversationId, onConversation, onLearned }:
  { student: Student; conversationId: number | null; onConversation: (id: number | null) => void; onLearned: () => void }) {
  const [msgs, setMsgs] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState(""); const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null); const taRef = useRef<HTMLTextAreaElement>(null);
  const cidRef = useRef<number | null>(conversationId);

  useEffect(() => {
    cidRef.current = conversationId;
    if (conversationId) getMessages(student.id, conversationId).then(setMsgs).catch(() => setMsgs([]));
    else setMsgs([]);
  }, [conversationId, student.id]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, status]);

  async function send(text: string) {
    text = text.trim(); if (!text || busy) return;
    setInput(""); setBusy(true); setStatus("Thinking…");
    setMsgs(m => [...m, { role: "user", content: text }]);
    try {
      await streamChat(student.id, text, cidRef.current, e => {
        if (e.type === "status") setStatus(e.label);
        if (e.type === "error") throw new Error(e.message);
        if (e.type === "final") {
          if (cidRef.current !== e.conversation_id) { cidRef.current = e.conversation_id; onConversation(e.conversation_id); }
          setMsgs(m => [...m, { role: "assistant", content: e.reply, agent: e.agent, payload: e.payload }]);
          onLearned();
        }
      });
    } catch (err: any) {
      setMsgs(m => [...m, { role: "assistant", agent: "system", content: `⚠️ ${err.message || "Something went wrong."} Is the backend running?` }]);
    } finally { setBusy(false); setStatus(null); taRef.current?.focus(); }
  }

  const lastIdx = msgs.length - 1;
  return (
    <section className="flex-1 flex flex-col min-w-0 h-full">
      <div className="flex-1 overflow-y-auto scroll-thin px-4 md:px-8 py-6">
        <div className="mx-auto max-w-3xl space-y-5">
          {msgs.length === 0 && (
            <div className="animate-rise pt-10 md:pt-20 text-center">
              <div className="mx-auto w-14 h-14 rounded-2xl bg-pine text-cap grid place-items-center shadow-lg"><Sparkles /></div>
              <h1 className="font-serif text-3xl md:text-4xl mt-5">What do you want to learn, {student.name.split(" ")[0]}?</h1>
              <p className="text-moss mt-2">Ask anything — a team of specialist tutors will pick up from here.</p>
              <div className="mt-8 flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map(s => (
                  <button key={s} onClick={() => send(s)} className="px-4 py-2 rounded-full bg-sheet border border-mist text-sm hover:border-moss hover:-translate-y-0.5 transition">{s}</button>
                ))}
              </div>
            </div>
          )}
          {msgs.map((m, i) => {
            if (m.role === "user") return (
              <div key={i} className="flex justify-end animate-rise"><div className="max-w-[85%] rounded-2xl rounded-br-md bg-pine text-paper px-4 py-2.5 whitespace-pre-wrap">{m.content}</div></div>);
            const a = AGENTS[m.agent || "tutor"] || AGENTS.tutor;
            const mu = m.payload?.mastery_update;
            return (
              <div key={i} className="flex gap-3 animate-rise">
                <div className={`shrink-0 w-8 h-8 rounded-xl grid place-items-center ${a.tone}`}><a.Icon size={16} /></div>
                <div className="min-w-0 flex-1">
                  <div className="text-[11px] uppercase tracking-widest text-moss mb-1">{a.label} agent</div>
                  <div className="rounded-2xl rounded-tl-md bg-sheet border border-mist px-4 py-3 shadow-sm"><Markdown>{m.content}</Markdown>
                    {m.payload?.cards && <Flashcards cards={m.payload.cards} />}
                  </div>
                  {mu && (
                    <div className="mt-2 inline-flex items-center gap-1.5 text-xs rounded-full bg-mist px-3 py-1">
                      {mu.after >= mu.before ? <TrendingUp size={13} /> : <TrendingDown size={13} className="text-berry" />}
                      <span><b>{mu.concept}</b> {Math.round(mu.before * 100)}% → {Math.round(mu.after * 100)}%</span>
                    </div>)}
                  {m.payload?.options && i === lastIdx && !busy && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {m.payload.options.map(o => (
                        <button key={o} onClick={() => send(o)} className="text-left px-3.5 py-2 rounded-xl border border-moss/40 bg-sheet text-sm hover:bg-pine hover:text-paper transition">{o}</button>))}
                    </div>)}
                </div>
              </div>);
          })}
          {busy && (
            <div className="flex items-center gap-2 text-sm text-moss animate-rise">
              <span className="flex gap-1">{[0, 1, 2].map(d => <i key={d} className="w-1.5 h-1.5 rounded-full bg-moss animate-dot" style={{ animationDelay: `${d * 0.2}s` }} />)}</span>{status}
            </div>)}
          <div ref={endRef} />
        </div>
      </div>
      <div className="px-4 md:px-8 pb-5 pt-2">
        <form onSubmit={e => { e.preventDefault(); send(input); }} className="mx-auto max-w-3xl flex items-end gap-2 rounded-3xl bg-sheet border border-mist shadow-md p-2 focus-within:border-moss transition">
          <textarea ref={taRef} value={input} rows={1} placeholder="Ask, answer, or say what you want to practise…"
            onChange={e => { setInput(e.target.value); e.target.style.height = "auto"; e.target.style.height = Math.min(e.target.scrollHeight, 160) + "px"; }}
            onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }}
            className="flex-1 resize-none bg-transparent outline-none px-3 py-2 max-h-40 placeholder:text-moss/60" />
          <button disabled={busy || !input.trim()} className="w-10 h-10 rounded-full bg-cap text-pine grid place-items-center disabled:opacity-40 hover:brightness-95 transition" aria-label="Send"><ArrowUp size={18} /></button>
        </form>
        <p className="text-center text-[11px] text-moss/70 mt-2">Educap teaches — it isn't a doctor. Clinical cases are educational simulations.</p>
      </div>
    </section>
  );
}
