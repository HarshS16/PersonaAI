"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useMe } from "@/hooks/use-auth";
import { authApi, type Me } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function SettingsPage() {
  const { data: me, isLoading } = useMe();

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Settings</h2>
        <p className="mt-1 text-muted-foreground">Account, privacy, and data ownership.</p>
      </div>

      {isLoading || !me ? (
        <Skeleton className="h-48 w-full" />
      ) : (
        <>
          <ProfileCard me={me} />
          <ChangePasswordCard />
          <ConnectedLoginsCard me={me} />
        </>
      )}
    </div>
  );
}

function ProfileCard({ me }: { me: Me }) {
  const qc = useQueryClient();
  const [name, setName] = useState(me.name ?? "");
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      await authApi.updateProfile(name);
      await qc.invalidateQueries({ queryKey: ["me"] });
      toast.success("Profile updated");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Update failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Profile</CardTitle>
        <CardDescription>
          {me.email}
          <Badge variant={me.email_verified ? "secondary" : "outline"} className="ml-2">
            {me.email_verified ? "verified" : "unverified"}
          </Badge>
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="name">Name</Label>
          <Input id="name" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <Button onClick={save} disabled={saving}>
          {saving ? "Saving…" : "Save profile"}
        </Button>
      </CardContent>
    </Card>
  );
}

function ChangePasswordCard() {
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [saving, setSaving] = useState(false);

  async function change() {
    setSaving(true);
    try {
      await authApi.changePassword(currentPw, newPw);
      setCurrentPw("");
      setNewPw("");
      toast.success("Password changed");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Change failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Change password</CardTitle>
        <CardDescription>Updating your password signs out other sessions.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="current">Current password</Label>
          <Input
            id="current"
            type="password"
            value={currentPw}
            onChange={(e) => setCurrentPw(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="new">New password</Label>
          <Input id="new" type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} />
        </div>
        <Button onClick={change} disabled={saving || !currentPw || newPw.length < 8}>
          {saving ? "Saving…" : "Change password"}
        </Button>
      </CardContent>
    </Card>
  );
}

function ConnectedLoginsCard({ me }: { me: Me }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Connected logins</CardTitle>
        <CardDescription>OAuth providers linked to your account.</CardDescription>
      </CardHeader>
      <CardContent>
        {me.oauth_accounts.length > 0 ? (
          <ul className="space-y-2">
            {me.oauth_accounts.map((a) => (
              <li key={a.provider} className="flex items-center justify-between text-sm">
                <span className="capitalize">{a.provider}</span>
                <span className="text-muted-foreground">{a.provider_username}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No connected logins.</p>
        )}
        <p className="mt-4 text-xs text-muted-foreground">
          Data export and account deletion arrive in M8.
        </p>
      </CardContent>
    </Card>
  );
}
