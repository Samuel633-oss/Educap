const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Reply = { conversation_id: string; agent: string; reply: string };

// Phase 1-2: a random id in localStorage identifies the student. Replace with real auth later.
export function studentId(): string {
  let id = localStorage.getItem("educap_student");
  if (!id) { id = crypto.randomUUID(); localStorage.setItem("educap_student", id); }
  return id;
}

export async function sendMessage(message: string, conversationId: string | null): Promise<Reply> {
  const res = await fetch(`${API}/api/chat`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ student_id: studentId(), message, conversation_id: conversationId }),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? "Something went wrong");
  return res.json();
}
