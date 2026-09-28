export type Student = { id: number; name: string };
export type Flashcard = { front: string; back: string };
export type Payload = {
  type?: "options" | "flashcards";
  options?: string[];
  cards?: Flashcard[];
  mastery_update?: { concept: string; before: number; after: number; attempts: number };
} | null;
export type ChatMessage = { role: "user" | "assistant"; content: string; agent?: string | null; payload?: Payload };
export type Mastery = { id: number; subject: string; topic: string; concept: string; mastery_score: number; confidence: number; attempts: number; correct_answers: number; incorrect_answers: number; last_reviewed: string | null };
export type MemoryItem = { id: number; type: string; content: string; importance: number };
export type DocItem = { id: number; title: string; subject: string; chunks: number; source: string };
export type ConversationItem = { id: number; title: string; updated_at: string };
export type ChatEvent =
  | { type: "status"; agent: string; label: string }
  | { type: "final"; conversation_id: number; reply: string; agent: string; intent: string; subject: string; topic: string; payload: Payload }
  | { type: "error"; message: string };
