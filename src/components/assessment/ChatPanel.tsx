import { useState, useRef, useEffect } from "react";
import { ChatMessage } from "@/types/assessment";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { MarkdownText } from "@/components/ui/markdown-text";
import { Send, Loader2, FileText } from "lucide-react";
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

    const { reply, sources } = await chatWithAI(text.trim(), checklistJson, assessmentId);
    const assistantMsg: ChatMessage = { role: "assistant", content: reply, timestamp: new Date().toISOString(), sources };
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
          <div key={i} className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}>
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
            {msg.role === "assistant" && msg.sources && msg.sources.length > 0 && (
              <div className="max-w-[80%] mt-1.5 flex flex-wrap gap-1.5">
                {Array.from(new Set(msg.sources.map((s) => s.document))).map((docName) => (
                  <span
                    key={docName}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-accent/10 border border-accent/20 text-xs text-accent-foreground"
                    title={docName}
                  >
                    <FileText className="h-3 w-3 shrink-0 text-accent" />
                    <span className="truncate max-w-[180px]">{docName}</span>
                  </span>
                ))}
              </div>
            )}
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
