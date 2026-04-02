import { MessageSquare } from "lucide-react";

export const metadata = {
  title: "Chat — Kara AI Tax Advisor",
  description: "Chat with Kara, your AI tax advisor for India.",
};

export default function ChatPage() {
  return (
    <section className="flex flex-1 flex-col items-center justify-center py-32 px-4">
      <MessageSquare className="h-16 w-16 text-muted-foreground mb-6" aria-hidden="true" />
      <h1 className="text-2xl font-semibold text-foreground mb-2">Chat Interface</h1>
      <p className="text-muted-foreground text-base text-center max-w-sm">
        Chat interface coming soon. The conversational tax advisor is under active development.
      </p>
    </section>
  );
}
