"use client";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { sendMessage } from "@/lib/api";

type Msg = { role: "user" | "assistant" | "error"; text: string; agent?: string };

const AGENT_LABEL: Record<string, string> = { tutor: "Tutor", socratic: "Socratic coach", exam: "Quiz master" };
const STARTERS = [
  "Teach me photosynthesis",
  "Explain derivatives like I'm new to calculus",
  "Quiz me on human anatomy",
  "I don't understand recursion",
];

export default function Chat() {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [conv, setConv] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => end.current?.scrollIntoView({ behavior: "smooth" }), [msgs, busy]);

  async function send(text: string) {
    const t = text.trim();
    if (!t || busy) return;
    setMsgs(m => [...m, { role: "user", text: t }]); setInput(""); setBusy(true);
    try {
      const r = await sendMessage(t, conv);
      setConv(r.conversation_id);
      setMsgs(m => [...m, { role: "assistant", text: r.reply, agent: r.agent }]);
    } catch (e) {
      setMsgs(m => [...m, { role: "error", text: `${(e as Error).message}. Check that the backend is running and your API key is set, then send again.` }]);
    } finally { setBusy(false); }
  }

  return (
    <div className="flex h-dvh">
      <aside className="hidden w-64 shrink-0 flex-col justify-between border-r border-mist bg-pine p-6 text-paper md:flex">
        <div>
          <div className="flex items-center gap-2.5">
            <svg width="30" height="30" viewBox="0 0 32 32" aria-hidden><path d="M16 5 2 12l14 7 11-5.5V22h2v-9.5z" fill="#F0B429"/><path d="M8 17v5c0 2 4 4 8 4s8-2 8-4v-5l-8 4z" fill="#F2F6F1"/></svg>
            <span className="text-2xl font-semibold tracking-tight">Educap</span>
          </div>
          <p className="mt-4 text-sm leading-relaxed text-mist/80">One conversation. A team of tutors behind it that explains, questions, and tests you.</p>
        </div>
        <button onClick={() => { setMsgs([]); setConv(null); }}
          className="rounded-lg border border-mist/30 px-4 py-2.5 text-left text-sm hover:bg-white/10">New session</button>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <div className="flex-1 overflow-y-auto px-4 py-8">
          <div className="mx-auto max-w-[44rem] space-y-6">
            {msgs.length === 0 && (
              <div className="pt-[12vh]">
                <h1 className="text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">What are we learning today?</h1>
                <p className="mt-3 max-w-md font-serif text-lg text-moss">Ask about any subject. Educap picks the right kind of help for you.</p>
                <ul className="mt-8 divide-y divide-mist border-y border-mist">
                  {STARTERS.map(s => (
                    <li key={s}><button onClick={() => send(s)} className="w-full py-3.5 text-left text-lg hover:bg-sheet hover:pl-2 transition-[padding]">{s}</button></li>
                  ))}
                </ul>
              </div>
            )}
            {msgs.map((m, i) => m.role === "user" ? (
              <div key={i} className="flex justify-end"><p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-pine px-4 py-2.5 text-paper">{m.text}</p></div>
            ) : m.role === "error" ? (
              <p key={i} role="alert" className="rounded-lg border border-berry/40 bg-berry/5 px-4 py-3 text-sm text-berry">{m.text}</p>
            ) : (
              <div key={i}>
                <div className="mb-1.5 flex items-center gap-2 text-sm font-medium text-moss"><span className="h-2 w-2 rounded-full bg-cap" />{AGENT_LABEL[m.agent ?? "tutor"]}</div>
                <div className="prose-tutor rounded-2xl rounded-tl-md border border-mist bg-sheet px-5 py-4 font-serif text-[1.08rem] leading-[1.7]"><ReactMarkdown>{m.text}</ReactMarkdown></div>
              </div>
            ))}
            {busy && <div className="flex items-center gap-2 text-sm text-moss" role="status">Choosing the right tutor <span className="flex gap-1"><i className="dot h-1.5 w-1.5 rounded-full bg-moss"/><i className="dot h-1.5 w-1.5 rounded-full bg-moss"/><i className="dot h-1.5 w-1.5 rounded-full bg-moss"/></span></div>}
            <div ref={end} />
          </div>
        </div>

        <div className="px-4 pb-5">
          <div className="mx-auto flex max-w-[44rem] items-end gap-2 rounded-2xl border border-mist bg-sheet p-2 focus-within:border-pine">
            <textarea value={input} onChange={e => setInput(e.target.value)} rows={1} aria-label="Message"
              onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }}
              placeholder="Ask, answer, or say what you're stuck on"
              className="max-h-40 flex-1 resize-none bg-transparent px-3 py-2 outline-none placeholder:text-moss/60 focus-visible:outline-none" />
            <button onClick={() => send(input)} disabled={busy || !input.trim()}
              className="rounded-xl bg-cap px-5 py-2.5 font-semibold text-pine disabled:opacity-40">Send</button>
          </div>
          <p className="mx-auto mt-2 max-w-[44rem] text-center text-xs text-moss">Educap teaches; it doesn't give medical advice. Clinical cases are practice scenarios.</p>
        </div>
      </main>
    </div>
  );
}
