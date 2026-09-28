import type { ChatEvent, ConversationItem, DocItem, Mastery, MemoryItem, Student, ChatMessage } from "./types";

export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `Request failed (${res.status})`);
  return res.json();
}
const post = (path: string, body: unknown) =>
  fetch(`${API}/api${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const createStudent = (name: string) => post("/students", { name }).then(r => j<Student>(r));
export const getMastery = (id: number) => fetch(`${API}/api/students/${id}/mastery`).then(r => j<Mastery[]>(r));
export const getMemories = (id: number) => fetch(`${API}/api/students/${id}/memories`).then(r => j<MemoryItem[]>(r));
export const deleteMemory = (id: number, mid: number) => fetch(`${API}/api/students/${id}/memories/${mid}`, { method: "DELETE" });
export const getDocs = (id: number) => fetch(`${API}/api/students/${id}/documents`).then(r => j<DocItem[]>(r));
export const deleteDoc = (id: number, did: number) => fetch(`${API}/api/students/${id}/documents/${did}`, { method: "DELETE" });
export const addTextDoc = (id: number, title: string, text: string, subject: string) =>
  post(`/students/${id}/documents`, { title, text, subject }).then(r => j<{ id: number }>(r));
export const uploadDoc = (id: number, file: File, subject: string) => {
  const f = new FormData(); f.append("file", file); f.append("subject", subject);
  return fetch(`${API}/api/students/${id}/documents/upload`, { method: "POST", body: f }).then(r => j<{ id: number }>(r));
};
export const getConversations = (id: number) => fetch(`${API}/api/students/${id}/conversations`).then(r => j<ConversationItem[]>(r));
export const getMessages = (id: number, cid: number) => fetch(`${API}/api/students/${id}/conversations/${cid}`).then(r => j<ChatMessage[]>(r));

/** Streams newline-delimited JSON events: status updates, then the final reply. */
export async function streamChat(studentId: number, message: string, conversationId: number | null, onEvent: (e: ChatEvent) => void) {
  const res = await post("/chat/stream", { student_id: studentId, message, conversation_id: conversationId });
  if (!res.ok || !res.body) throw new Error((await res.json().catch(() => ({}))).detail || "Could not reach the tutor");
  const reader = res.body.getReader(); const dec = new TextDecoder(); let buf = "";
  for (;;) {
    const { done, value } = await reader.read(); if (done) break;
    buf += dec.decode(value, { stream: true });
    let i: number;
    while ((i = buf.indexOf("\n")) >= 0) { const line = buf.slice(0, i).trim(); buf = buf.slice(i + 1); if (line) onEvent(JSON.parse(line)); }
  }
}
