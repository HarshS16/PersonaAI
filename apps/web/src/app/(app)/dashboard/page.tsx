"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { MessagesSquare, FileText, Target, Network, Briefcase } from "lucide-react";
import { dashboardApi } from "@/lib/dashboard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { OnboardingCard } from "@/components/dashboard/onboarding-card";

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

export default function DashboardPage() {
  const { data, isLoading } = useQuery({ queryKey: ["dashboard"], queryFn: dashboardApi.get });

  if (isLoading || !data) {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  const pct = Math.round(data.completeness * 100);
  const showOnboarding = !data.has_sources || data.completeness < 0.4;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">
          {greeting()}
          {data.greeting_name ? `, ${data.greeting_name.split(" ")[0]}` : ""}
        </h2>
        <p className="mt-1 text-muted-foreground">Here&apos;s your professional persona at a glance.</p>
      </div>

      {showOnboarding && <OnboardingCard data={data} />}

      <div className="rounded-lg border p-4">
        <div className="mb-2 flex items-center justify-between text-sm">
          <span className="font-medium">Persona completeness</span>
          <span className="text-muted-foreground">{pct}%</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${pct}%` }} />
        </div>
        <div className="mt-3 flex flex-wrap gap-4 text-sm text-muted-foreground">
          <span>{data.counts.skills} skills</span>
          <span>{data.counts.projects} projects</span>
          <span>{data.counts.experiences} roles</span>
          <span>{data.counts.sources} sources</span>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle className="text-base">Top skills</CardTitle>
            <Link href="/persona" className="text-xs text-primary hover:underline">
              Edit
            </Link>
          </CardHeader>
          <CardContent>
            {data.top_skills.length === 0 ? (
              <p className="text-sm text-muted-foreground">No skills yet.</p>
            ) : (
              <div className="flex flex-wrap gap-1">
                {data.top_skills.map((s) => (
                  <Badge key={s.id} variant="secondary">
                    {s.name}
                  </Badge>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle className="text-base">Experience</CardTitle>
            <Briefcase className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {data.timeline.length === 0 ? (
              <p className="text-sm text-muted-foreground">No experience yet.</p>
            ) : (
              <ul className="space-y-2">
                {data.timeline.slice(0, 3).map((e) => (
                  <li key={e.id} className="text-sm">
                    <span className="font-medium">{e.role}</span>
                    {e.company && <span className="text-muted-foreground"> · {e.company}</span>}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      {data.recent_activity.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recent updates</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {data.recent_activity.map((a, i) => (
                <li key={i} className="flex items-center justify-between text-sm">
                  <span>{a.text}</span>
                  {a.at && (
                    <span className="text-xs text-muted-foreground">
                      {new Date(a.at).toLocaleDateString()}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <div>
        <h3 className="mb-2 text-sm font-medium text-muted-foreground">Quick actions</h3>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <QuickAction href="/ask" icon={MessagesSquare} label="Ask My Persona" />
          <QuickAction href="/career" icon={FileText} label="Create Resume" />
          <QuickAction href="/career" icon={Target} label="Analyze JD" />
          <QuickAction href="/persona/explorer" icon={Network} label="Explore Persona" />
        </div>
      </div>
    </div>
  );
}

function QuickAction({
  href,
  icon: Icon,
  label,
}: {
  href: string;
  icon: typeof MessagesSquare;
  label: string;
}) {
  return (
    <Link
      href={href}
      className="flex items-center gap-2 rounded-md border px-4 py-3 text-sm font-medium transition-colors hover:bg-muted"
    >
      <Icon className="h-4 w-4" />
      {label}
    </Link>
  );
}
