import type { ReactNode } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export function PagePlaceholder({
  title,
  description,
  milestone,
  children,
}: {
  title: string;
  description: string;
  milestone: string;
  children?: ReactNode;
}) {
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
          <p className="mt-1 text-muted-foreground">{description}</p>
        </div>
        <Badge variant="secondary">{milestone}</Badge>
      </div>
      {children ?? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Coming together</CardTitle>
            <CardDescription>
              This surface is scaffolded. Functionality lands in {milestone}.
            </CardDescription>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            The app shell, routing, and backend foundations are in place.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
