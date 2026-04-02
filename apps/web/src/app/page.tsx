import Link from "next/link";
import { ArrowRight, ExternalLink, MessageSquare, Calculator, Code, Shield } from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const features = [
  {
    icon: MessageSquare,
    title: "Conversational",
    description:
      "Ask questions in plain English. Kara asks clarifying questions before computing, just like a real tax advisor.",
  },
  {
    icon: Calculator,
    title: "Deterministic",
    description:
      "Tax computations use a certified rule engine with 300+ test cases. No hallucination, no guessing.",
  },
  {
    icon: Code,
    title: "Open Source",
    description:
      "MIT licensed rule engine. AGPL-3.0 platform. Fully auditable, community-driven, self-hostable.",
  },
  {
    icon: Shield,
    title: "Privacy First",
    description:
      "Your financial data stays on your machine. Bring your own LLM API key. No data leaves your infrastructure.",
  },
];

const steps = [
  {
    number: "1",
    title: "Ask",
    description:
      "Type your tax question naturally. 'How much tax do I owe on 15 lakh salary?'",
  },
  {
    number: "2",
    title: "Compute",
    description:
      "Our rule engine calculates using FY 2025-26 rules — 7 slabs, 87A rebate, surcharge, cess.",
  },
  {
    number: "3",
    title: "Advise",
    description:
      "Get a breakdown with proactive tips. 'Switch to new regime to save \u20b945,000.'",
  },
];

const techStack = ["Python", "FastAPI", "Next.js", "PostgreSQL", "pgvector"];

export default function Home() {
  return (
    <>
      {/* Section 1: Hero */}
      <section className="bg-gradient-to-b from-background to-muted/30 py-20 md:py-32">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="max-w-3xl mx-auto text-center">
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight text-foreground">
              Your AI Tax Advisor for India
            </h1>
            <p className="mt-6 text-lg md:text-xl text-muted-foreground leading-relaxed">
              Get accurate tax computations, regime comparisons, and personalized deduction advice.
              Powered by deterministic rules, guided by AI. Free and open source.
            </p>
            <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/chat"
                className="inline-flex items-center justify-center h-12 px-8 text-lg font-medium rounded-lg bg-kara-cta hover:bg-kara-cta-hover text-white transition-colors w-full sm:w-auto"
              >
                Start Chatting
                <ArrowRight className="ml-2 h-5 w-5" />
              </Link>
              <a
                href="https://github.com/anthropics/kara"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center h-12 px-8 text-lg font-medium rounded-lg border border-border bg-background hover:bg-muted text-foreground transition-colors w-full sm:w-auto"
              >
                View on GitHub
                <ExternalLink className="ml-2 h-4 w-4" />
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* Section 2: Features Grid */}
      <section className="py-16 md:py-24">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-center text-foreground mb-12">
            Why Kara?
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {features.map((feature) => {
              const Icon = feature.icon;
              return (
                <Card
                  key={feature.title}
                  className="transition-shadow hover:shadow-md"
                >
                  <CardHeader>
                    <div className="mb-2">
                      <Icon className="text-kara-primary" size={32} />
                    </div>
                    <CardTitle className="font-semibold text-foreground">
                      {feature.title}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <CardDescription className="text-muted-foreground text-base">
                      {feature.description}
                    </CardDescription>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      </section>

      {/* Section 3: How It Works */}
      <section className="py-16 md:py-24 bg-muted/30">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-center text-foreground mb-12">
            How It Works
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 md:gap-6">
            {steps.map((step, index) => (
              <div key={step.title} className="relative flex flex-col items-center text-center">
                {/* Connector line for desktop — shown between steps */}
                {index < steps.length - 1 && (
                  <div
                    className="hidden md:block absolute top-6 left-[calc(50%+2.5rem)] w-[calc(100%-5rem)] border-t-2 border-dashed border-border"
                    aria-hidden="true"
                  />
                )}
                <div className="w-12 h-12 rounded-full bg-kara-primary text-white flex items-center justify-center font-bold text-lg shrink-0 z-10">
                  {step.number}
                </div>
                <h3 className="mt-4 font-semibold text-xl text-foreground">
                  {step.title}
                </h3>
                <p className="mt-2 text-muted-foreground text-base leading-relaxed">
                  {step.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Section 4: Tech Stack */}
      <section className="py-12 md:py-16">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl font-semibold text-center text-foreground mb-8">
            Built With
          </h2>
          <div className="flex flex-wrap justify-center gap-2">
            {techStack.map((tech) => (
              <Badge key={tech} variant="secondary" className="text-sm px-3 py-1">
                {tech}
              </Badge>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
