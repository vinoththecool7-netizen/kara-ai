import type { Metadata } from "next";
import { ChatWindow } from "@/components/chat/ChatWindow";

export const metadata: Metadata = {
  title: "Chat — Kara AI Tax Advisor",
  description: "Chat with Kara, your AI tax advisor for India.",
};

export default function ChatPage() {
  return (
    <div className="flex flex-col flex-1 h-full">
      <ChatWindow />
    </div>
  );
}
