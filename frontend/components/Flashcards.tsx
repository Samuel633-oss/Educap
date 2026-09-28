"use client";
import { useState } from "react";
import { ChevronLeft, ChevronRight, RotateCw } from "lucide-react";
import type { Flashcard } from "@/lib/types";

export default function Flashcards({ cards }: { cards: Flashcard[] }) {
  const [i, setI] = useState(0); const [flipped, setFlipped] = useState(false);
  const go = (d: number) => { setFlipped(false); setI((i + d + cards.length) % cards.length); };
  const c = cards[i];
  return (
    <div className="mt-3 max-w-md">
      <button onClick={() => setFlipped(!flipped)} className="flip block w-full text-left" aria-label="Flip card">
        <div className={`flip-inner relative h-44 ${flipped ? "on" : ""}`}>
          <div className="flip-face absolute inset-0 rounded-2xl bg-pine text-paper p-5 flex flex-col justify-between shadow-md">
            <span className="text-[11px] uppercase tracking-widest text-cap">Question</span>
            <p className="font-serif text-lg leading-snug">{c.front}</p>
            <span className="text-xs text-mist/70 flex items-center gap-1"><RotateCw size={12} /> tap to flip</span>
          </div>
          <div className="flip-face flip-back absolute inset-0 rounded-2xl bg-cap/90 text-pine p-5 flex flex-col justify-between shadow-md">
            <span className="text-[11px] uppercase tracking-widest">Answer</span>
            <p className="text-base leading-snug">{c.back}</p>
            <span />
          </div>
        </div>
      </button>
      <div className="mt-2 flex items-center justify-between text-sm text-moss">
        <button onClick={() => go(-1)} className="p-1.5 rounded-lg hover:bg-mist"><ChevronLeft size={18} /></button>
        <span>{i + 1} / {cards.length}</span>
        <button onClick={() => go(1)} className="p-1.5 rounded-lg hover:bg-mist"><ChevronRight size={18} /></button>
      </div>
    </div>
  );
}
