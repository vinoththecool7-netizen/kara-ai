"use client";

import { ScrollArea } from "@/components/ui/scroll-area";
import { MessageInput } from "./MessageInput";

export function ChatWindow() {
  function handleSend(text: string) {
    console.log("User message:", text);
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div className="flex-1 overflow-hidden">
        <ScrollArea className="h-full">
          <div className="max-w-3xl mx-auto w-full px-4 py-8 flex items-center justify-center min-h-[200px]">
            <p className="text-muted-foreground text-sm">Messages will appear here</p>
          </div>
        </ScrollArea>
      </div>

      {/* Input area */}
      <MessageInput onSend={handleSend} />
    </div>
  );
}
