import type { Metadata } from "next";
import Link from "next/link";
import { Home, MessageSquare } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export const metadata: Metadata = {
  title: "Not found",
  robots: { index: false, follow: false },
};

export default function NotFound() {
  return (
    <div className="flex flex-1 items-center justify-center px-4 py-24">
      <Card className="w-full max-w-md text-center">
        <CardHeader>
          <p
            className="text-7xl font-bold tracking-tight text-kara-primary"
            aria-hidden="true"
          >
            404
          </p>
          <CardTitle className="text-2xl">Page not found</CardTitle>
          <CardDescription>
            The page you&apos;re looking for doesn&apos;t exist or has moved.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col sm:flex-row gap-2 justify-center">
          <Button render={<Link href="/" />} variant="default">
            <Home className="size-4" aria-hidden="true" />
            Back to home
          </Button>
          <Button render={<Link href="/chat" />} variant="outline">
            <MessageSquare className="size-4" aria-hidden="true" />
            Start a chat
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
