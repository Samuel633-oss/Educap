"use client";
import { useEffect, useRef, useState } from "react";
import { BarChart3, FileText, History, Plus, Trash2, Upload, Brain, X } from "lucide-react";
import { addTextDoc, deleteDoc, deleteMemory, getConversations, getDocs, getMastery, getMemories, uploadDoc } from "@/lib/api";
import type { ConversationItem, DocItem, Mastery, MemoryItem, Student } from "@/lib/types";

type Tab = "progress" | "memory" | "materials" | "history";
const pct = (n: number) => Math.round(n * 100);

function ProgressTab({ rows }: { rows: Mastery[] }) {
  if (!rows.length) return <Empty text="Answer a few quiz questions and your mastery will show up here." />;
  const byTopic = rows.reduce<Record<string, Mastery[]>>((a, r) => { (a[`${r.subject} · ${r.topic}`] ||= []).push(r); return a; }, {});
  return (<div className="space-y-5">{Object.entries(byTopic).map(([k, list]) => (
    <div key={k}><div className="text-[11px] uppercase tracking-widest text-mist/60 mb-2">{k}</div>
      <div className="space-y-2.5">{list.map(r => (
        <div key={r.id}><div className="flex justify-between text-sm"><span>{r.concept}</span><span className="text-mist/80">{pct(r.mastery_score)}%</span></div>
          <div className="h-1.5 rounded-full bg-paper/10 mt-1"><div className={`h-full rounded-full ${r.mastery_score >= 0.8 ? "bg-emerald-300" : r.mastery_score >= 0.6 ? "bg-cap" : "bg-rose-300"}`} style={{ width: `${pct(r.mastery_score)}%` }} /></div></div>))}
      </div></div>))}</div>);
}
const Empty = ({ text }: { text: string }) => <p className="text-sm text-mist/60 leading-relaxed">{text}</p>;

function MemoryTab({ id, rows, reload }: { id: number; rows: MemoryItem[]; reload: () => void }) {
  if (!rows.length) return <Empty text="Educap remembers useful things about how you learn — preferences, goals, recurring struggles. Nothing yet." />;
  return (<ul className="space-y-2">{rows.map(m => (
    <li key={m.id} className="group rounded-xl bg-paper/5 p-3 text-sm"><div className="flex justify-between gap-2">
      <span className="text-[10px] uppercase tracking-widest text-cap">{m.type}</span>
      <button onClick={() => deleteMemory(id, m.id).then(reload)} className="opacity-0 group-hover:opacity-100 text-mist/60 hover:text-rose-300" aria-label="Forget"><Trash2 size={13} /></button></div>
      <p className="mt-1 text-mist">{m.content}</p></li>))}</ul>);
}

function MaterialsTab({ id, docs, reload }: { id: number; docs: DocItem[]; reload: () => void }) {
  const [title, setTitle] = useState(""); const [text, setText] = useState(""); const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  const file = useRef<HTMLInputElement>(null);
  async function run(fn: () => Promise<unknown>) { setBusy(true); setErr(""); try { await fn(); reload(); setTitle(""); setText(""); } catch (e: any) { setErr(e.message); } finally { setBusy(false); } }
  return (<div className="space-y-4">
    <p className="text-sm text-mist/70">Add your notes or a PDF. Educap retrieves only the relevant parts when it teaches you.</p>
    <input value={title} onChange={e => setTitle(e.target.value)} placeholder="Title (e.g. Biology ch.4)" className="w-full rounded-lg bg-paper/10 px-3 py-2 text-sm outline-none placeholder:text-mist/40" />
    <textarea value={text} onChange={e => setText(e.target.value)} rows={4} placeholder="Paste notes here…" className="w-full rounded-lg bg-paper/10 px-3 py-2 text-sm outline-none placeholder:text-mist/40 resize-none" />
    <div className="flex gap-2">
      <button disabled={busy || !title.trim() || text.trim().length < 10} onClick={() => run(() => addTextDoc(id, title, text, "General"))} className="flex-1 rounded-lg bg-cap text-pine text-sm font-medium py-2 disabled:opacity-40">Add notes</button>
      <button disabled={busy} onClick={() => file.current?.click()} className="rounded-lg bg-paper/10 px-3 grid place-items-center" aria-label="Upload file"><Upload size={16} /></button>
      <input ref={file} type="file" accept=".txt,.md,.pdf" hidden onChange={e => { const f = e.target.files?.[0]; if (f) run(() => uploadDoc(id, f, "General")); e.target.value = ""; }} />
    </div>
    {err && <p className="text-xs text-rose-300">{err}</p>}
    <ul className="space-y-2">{docs.map(d => (
      <li key={d.id} className="flex items-center gap-2 rounded-xl bg-paper/5 p-3 text-sm"><FileText size={15} className="text-cap shrink-0" />
        <div className="min-w-0 flex-1"><div className="truncate">{d.title}</div><div className="text-[11px] text-mist/60">{d.chunks} sections</div></div>
        <button onClick={() => deleteDoc(id, d.id).then(reload)} className="text-mist/50 hover:text-rose-300" aria-label="Delete"><Trash2 size={14} /></button></li>))}</ul>
  </div>);
}

export default function Sidebar({ student, activeId, refreshKey, onSelect, onNew, open, onClose, onSignOut }:
  { student: Student; activeId: number | null; refreshKey: number; onSelect: (id: number) => void; onNew: () => void; open: boolean; onClose: () => void; onSignOut: () => void }) {
  const [tab, setTab] = useState<Tab>("progress");
  const [mastery, setMastery] = useState<Mastery[]>([]); const [mem, setMem] = useState<MemoryItem[]>([]);
  const [docs, setDocs] = useState<DocItem[]>([]); const [convs, setConvs] = useState<ConversationItem[]>([]);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    getMastery(student.id).then(setMastery).catch(() => {}); getMemories(student.id).then(setMem).catch(() => {});
    getDocs(student.id).then(setDocs).catch(() => {}); getConversations(student.id).then(setConvs).catch(() => {});
  }, [student.id, refreshKey, tick]);
  const reload = () => setTick(t => t + 1);
  const tabs: [Tab, string, any][] = [["progress", "Progress", BarChart3], ["memory", "Memory", Brain], ["materials", "Notes", FileText], ["history", "Chats", History]];
  return (
    <>
      {open && <div className="fixed inset-0 bg-pine/50 z-30 md:hidden" onClick={onClose} />}
      <aside className={`fixed md:static z-40 inset-y-0 left-0 w-80 bg-pine text-paper flex flex-col transition-transform ${open ? "" : "-translate-x-full md:translate-x-0"}`}>
        <div className="p-5 flex items-center justify-between">
          <div className="flex items-center gap-2.5"><div className="w-9 h-9 rounded-xl bg-cap text-pine grid place-items-center font-serif text-xl font-bold">E</div>
            <div><div className="font-serif text-xl leading-none">Educap</div><div className="text-[11px] text-mist/60 mt-1">Hi, {student.name}</div></div></div>
          <button onClick={onClose} className="md:hidden text-mist/70"><X size={20} /></button>
        </div>
        <button onClick={() => { onNew(); onClose(); }} className="mx-5 mb-4 flex items-center justify-center gap-2 rounded-xl bg-paper/10 hover:bg-paper/20 py-2.5 text-sm transition"><Plus size={16} /> New chat</button>
        <div className="mx-5 grid grid-cols-4 rounded-xl bg-paper/5 p-1">
          {tabs.map(([k, label, Icon]) => (
            <button key={k} onClick={() => setTab(k)} className={`flex flex-col items-center gap-0.5 rounded-lg py-1.5 text-[10px] transition ${tab === k ? "bg-paper text-pine" : "text-mist/70 hover:text-paper"}`}><Icon size={15} />{label}</button>))}
        </div>
        <div className="flex-1 overflow-y-auto scroll-thin p-5">
          {tab === "progress" && <ProgressTab rows={mastery} />}
          {tab === "memory" && <MemoryTab id={student.id} rows={mem} reload={reload} />}
          {tab === "materials" && <MaterialsTab id={student.id} docs={docs} reload={reload} />}
          {tab === "history" && (convs.length ? <ul className="space-y-1.5">{convs.map(c => (
            <li key={c.id}><button onClick={() => { onSelect(c.id); onClose(); }} className={`w-full text-left truncate rounded-lg px-3 py-2 text-sm transition ${c.id === activeId ? "bg-paper/15" : "hover:bg-paper/10"}`}>{c.title}</button></li>))}</ul>
            : <Empty text="Your conversations will appear here." />)}
        </div>
        <button onClick={onSignOut} className="m-5 text-xs text-mist/50 hover:text-mist text-left">Switch student</button>
      </aside>
    </>
  );
}
