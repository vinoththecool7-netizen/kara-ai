import type { Metadata } from "next";
import { ChatLayout } from "@/components/chat/ChatLayout";
import { SITE_URL } from "@/lib/constants";

export const metadata: Metadata = {
  title: "Chat with Kara",
  openGraph: {
    title: "Chat with Kara — AI Tax Advisor for India",
    description: "Chat with Kara, your AI tax advisor for India.",
    url: `${SITE_URL}/chat`,
  },
  twitter: {
    title: "Chat with Kara — AI Tax Advisor for India",
    description: "Chat with Kara, your AI tax advisor for India.",
  },
};

export default function ChatPage() {
  return (
    <div className="flex flex-col flex-1 h-full">
      <ChatLayout />
    </div>
  );
}
