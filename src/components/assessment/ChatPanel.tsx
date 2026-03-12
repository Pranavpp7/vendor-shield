import { useState, useRef, useEffect } from "react";
import { ChatMessage } from "@/types/assessment";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { MarkdownText } from "@/components/ui/markdown-text";
import { Send, Loader2 } from "lucide-react";
import { chatWithAI } from "@/lib/api";

const QUICK_QUESTIONS = [
  "What are the top 3 risks for this vendor?",
  "Why is the score not higher?",
  "What follow-up questions should I send to the vendor?",
];

type Props = {
  chatHistory: ChatMessage[];
  checklistJson: string;
  onNewMessage: (messages: ChatMessage[]) => void;
  assessmentId?: string;
};

export function ChatPanel({ chatHistory, checklistJson, onNewMessage, assessmentId }: Props) {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [chatHistory]);

  const sendMessage = async (text: string) => {
    if (!text.trim() || loading) return;
    const userMsg: ChatMessage = { role: "user", content: text.trim(), timestamp: new Date().toISOString() };
    const updated = [...chatHistory, userMsg];
    onNewMessage(updated);
    setInput("");
    setLoading(true);

    const reply = await chatWithAI(text.trim(), checklistJson);
    const assistantMsg: ChatMessage = { role: "assistant", content: reply, timestamp: new Date().toISOString() };
    onNewMessage([...updated, assistantMsg]);
    setLoading(false);
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex gap-2 flex-wrap mb-4">
        {QUICK_QUESTIONS.map((q) => (
          <Button key={q} variant="outline" size="sm" onClick={() => setInput(q)} className="text-xs">
            {q}
          </Button>
        ))}
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-3 mb-4 min-h-[200px] max-h-[400px]">
        {chatHistory.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-8">
            Ask a question about this assessment…
          </p>
        )}
        {chatHistory.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2 text-sm ${
                msg.role === "user" ? "bg-primary text-primary-foreground whitespace-pre-wrap" : "bg-muted"
              }`}
            >
              {msg.role === "assistant" ? (
                <MarkdownText content={msg.content} />
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-muted rounded-lg px-4 py-2">
              <Loader2 className="h-4 w-4 animate-spin" />
            </div>
          </div>
        )}
      </div>

      <div className="flex gap-2">
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about this assessment…"
          className="min-h-[44px] max-h-[120px]"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              sendMessage(input);
            }
          }}
        />
        <Button onClick={() => sendMessage(input)} disabled={loading || !input.trim()} size="icon">
          <Send className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
