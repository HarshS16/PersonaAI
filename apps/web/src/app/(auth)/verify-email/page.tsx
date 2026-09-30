"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { authApi } from "@/lib/auth";

type Status = "pending" | "ok" | "error";

function Verify() {
  const token = useSearchParams().get("token") ?? "";
  const [status, setStatus] = useState<Status>(token ? "pending" : "error");
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current || !token) return;
    ran.current = true;
    authApi
      .verifyEmail(token)
      .then(() => setStatus("ok"))
      .catch(() => setStatus("error"));
  }, [token]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {status === "pending" && "Verifying…"}
          {status === "ok" && "Email verified"}
          {status === "error" && "Verification failed"}
        </CardTitle>
        <CardDescription>
          {status === "ok" && "Your email is confirmed."}
          {status === "error" && "This link is invalid or has expired."}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Link href="/dashboard" className="text-primary hover:underline">
          Go to dashboard
        </Link>
      </CardContent>
    </Card>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense>
      <Verify />
    </Suspense>
  );
}
