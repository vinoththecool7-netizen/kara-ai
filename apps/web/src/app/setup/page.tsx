import type { Metadata } from "next";
import { SetupWizard } from "@/components/setup/SetupWizard";

export const metadata: Metadata = {
  title: "Set up Kara",
  robots: { index: false },
};

export default function SetupPage() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <SetupWizard />
    </div>
  );
}
