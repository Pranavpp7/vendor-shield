import { useMemo } from "react";

/**
 * Renders a simple subset of markdown (bold, bullet lists, headers)
 * as proper HTML instead of showing raw ** and * characters.
 */
export function MarkdownText({ content }: { content: string }) {
  const html = useMemo(() => {
    let text = content;

    // Escape HTML
    text = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

    // Headers (### ## #)
    text = text.replace(/^### (.+)$/gm, '<h4 class="font-semibold text-sm mt-3 mb-1">$1</h4>');
    text = text.replace(/^## (.+)$/gm, '<h3 class="font-semibold text-base mt-3 mb-1">$1</h3>');
    text = text.replace(/^# (.+)$/gm, '<h2 class="font-bold text-lg mt-3 mb-1">$1</h2>');

    // Bold (**text** or __text__)
    text = text.replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold">$1</strong>');
    text = text.replace(/__(.+?)__/g, '<strong class="font-semibold">$1</strong>');

    // Italic (*text* or _text_) — only single asterisks not part of bold
    text = text.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, '<em>$1</em>');

    // Bullet lists (- or *)
    text = text.replace(/^[\*\-]\s+(.+)$/gm, '<li class="ml-4 list-disc">$1</li>');
    // Wrap consecutive <li> in <ul>
    text = text.replace(/((?:<li[^>]*>.*?<\/li>\n?)+)/g, '<ul class="space-y-0.5 my-1">$1</ul>');

    // Numbered lists
    text = text.replace(/^\d+\.\s+(.+)$/gm, '<li class="ml-4 list-decimal">$1</li>');
    text = text.replace(/((?:<li class="ml-4 list-decimal">.*?<\/li>\n?)+)/g, '<ol class="space-y-0.5 my-1">$1</ol>');

    // Line breaks (double newline = paragraph break, single = br)
    text = text.replace(/\n\n/g, '</p><p class="mt-2">');
    text = text.replace(/\n/g, "<br/>");

    return `<p>${text}</p>`;
  }, [content]);

  return (
    <div
      className="prose-sm max-w-none [&_strong]:text-inherit [&_h2]:text-inherit [&_h3]:text-inherit [&_h4]:text-inherit"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
