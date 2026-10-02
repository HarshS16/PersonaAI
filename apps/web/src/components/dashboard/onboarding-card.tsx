"use client";

import Link from "next/link";
import { Circle, CheckCircle2, Upload, UserPlus } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { DashboardData } from "@/lib/dashboard";

function GithubIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        d="M12 2C6.48 2 2 6.58 2 12.25c0 4.53 2.87 8.37 6.84 9.73.5.1.68-.22.68-.49 0-.24-.01-.87-.01-1.71-2.78.62-3.37-1.37-3.37-1.37-.46-1.18-1.11-1.5-1.11-1.5-.91-.64.07-.62.07-.62 1 .07 1.53 1.06 1.53 1.06.89 1.56 2.34 1.11 2.91.85.09-.66.35-1.11.63-1.37-2.22-.26-4.56-1.14-4.56-5.07 0-1.12.39-2.03 1.03-2.75-.1-.26-.45-1.3.1-2.71 0 0 .84-.28 2.75 1.05A9.3 9.3 0 0 1 12 6.84c.85 0 1.71.12 2.51.34 1.91-1.33 2.75-1.05 2.75-1.05.55 1.41.2 2.45.1 2.71.64.72 1.03 1.63 1.03 2.75 0 3.94-2.34 4.81-4.57 5.06.36.32.68.94.68 1.9 0 1.37-.01 2.47-.01 2.81 0 .27.18.59.69.49A10.02 10.02 0 0 0 22 12.25C22 6.58 17.52 2 12 2z"
      />
    </svg>
  );
}

export function OnboardingCard({ data }: { data: DashboardData }) {
  const hasResume = data.sources.some((s) => s.type === "resume");
  const hasGithub = data.sources.some((s) => s.type === "github");
  const hasManual = data.counts.skills + data.counts.experiences + data.counts.projects > 0;

  const steps = [
    { done: hasResume, label: "Upload your resume", icon: Upload, href: "/sources" },
    { done: hasGithub, label: "Connect GitHub", icon: GithubIcon, href: "/sources" },
    { done: hasManual, label: "Add details manually", icon: UserPlus, href: "/persona" },
  ];
  const doneCount = steps.filter((s) => s.done).length;

  return (
    <Card className="border-primary/30 bg-primary/5">
      <CardHeader>
        <CardTitle>Build your AI Persona</CardTitle>
        <CardDescription>
          Connect your professional identity once. Let AI use that context everywhere.
          {doneCount > 0 && ` · ${doneCount}/3 done`}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {steps.map((s) => {
          const Icon = s.icon;
          return (
            <Link
              key={s.label}
              href={s.href}
              className="flex items-center justify-between rounded-md border bg-background px-4 py-3 text-sm transition-colors hover:bg-muted"
            >
              <span className="flex items-center gap-3">
                {s.done ? (
                  <CheckCircle2 className="h-4 w-4 text-green-600" />
                ) : (
                  <Circle className="h-4 w-4 text-muted-foreground" />
                )}
                <Icon className="h-4 w-4 text-muted-foreground" />
                {s.label}
              </span>
              {!s.done && (
                <Button size="sm" variant="ghost">
                  Start
                </Button>
              )}
            </Link>
          );
        })}
      </CardContent>
    </Card>
  );
}
