"use client";
import { useEffect, useState } from "react";
import { Menu } from "lucide-react";
import Chat from "@/components/Chat";
import Sidebar from "@/components/Sidebar";
import { createStudent } from "@/lib/api";
import type { Student } from "@/lib/types";

const KEY = "educap_student";

function Welcome({ onDone }: { onDone: (s: Student) => void }) {
  const [name, setName] = useState(""); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  async function go(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setErr("");
    try { onDone(await createStudent(name.trim())); } catch (x: any) { setErr(`${x.message}. Is the backend running on port 8000?`); } finally { setBusy(false); }
  }
  return (
    <main className="min-h-screen grid place-items-center p-6 bg-gradient-to-br from-paper via-paper to-mist">
      <form onSubmit={go} className="w-full max-w-sm bg-sheet rounded-3xl shadow-xl border border-mist p-8 text-center animate-rise">
        <div className="mx-auto w-14 h-14 rounded-2xl bg-pine text-cap grid place-items-center font-serif text-3xl font-bold">E</div>
        <h1 className="font-serif text-3xl mt-4">Educap</h1>
        <p className="text-moss mt-1 text-sm">Your AI study team. It remembers how you learn.</p>
        <input autoFocus value={name} onChange={e => setName(e.target.value)} placeholder="What should we call you?" className="mt-6 w-full rounded-xl border border-mist bg-paper px-4 py-3 outline-none focus:border-moss" />
        <button disabled={!name.trim() || busy} className="mt-3 w-full rounded-xl bg-pine text-paper py-3 font-medium disabled:opacity-40 hover:brightness-110 transition">{busy ? "Starting…" : "Start learning"}</button>
        {err && <p className="text-xs text-berry mt-3">{err}</p>}
      </form>
    </main>
  );
}

export default function Home() {
  const [student, setStudent] = useState<Student | null>(null); const [ready, setReady] = useState(false);
  const [convId, setConvId] = useState<number | null>(null); const [refresh, setRefresh] = useState(0); const [open, setOpen] = useState(false);
  useEffect(() => { try { const s = localStorage.getItem(KEY); if (s) setStudent(JSON.parse(s)); } catch {} setReady(true); }, []);
  if (!ready) return null;
  if (!student) return <Welcome onDone={s => { localStorage.setItem(KEY, JSON.stringify(s)); setStudent(s); }} />;
  return (
    <div className="h-screen flex">
      <Sidebar student={student} activeId={convId} refreshKey={refresh} open={open} onClose={() => setOpen(false)}
        onSelect={setConvId} onNew={() => setConvId(null)} onSignOut={() => { localStorage.removeItem(KEY); setStudent(null); setConvId(null); }} />
      <div className="flex-1 flex flex-col min-w-0">
        <header className="md:hidden flex items-center gap-3 px-4 py-3 border-b border-mist bg-sheet">
          <button onClick={() => setOpen(true)} aria-label="Menu"><Menu size={22} /></button><span className="font-serif text-lg">Educap</span>
        </header>
        <Chat student={student} conversationId={convId} onConversation={setConvId} onLearned={() => setRefresh(r => r + 1)} />
      </div>
    </div>
  );
}
