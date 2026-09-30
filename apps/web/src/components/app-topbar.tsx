"use client";

import { usePathname, useRouter } from "next/navigation";
import { LogOut, Settings as SettingsIcon } from "lucide-react";
import { NAV_ITEMS } from "@/lib/nav";
import { useMe, useLogout } from "@/hooks/use-auth";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

function initials(name: string | null, email: string): string {
  if (name) {
    const parts = name.trim().split(/\s+/);
    return (parts[0]?.[0] ?? "" + (parts[1]?.[0] ?? "")).toUpperCase().slice(0, 2);
  }
  return email.slice(0, 2).toUpperCase();
}

export function AppTopbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { data: me } = useMe();
  const logout = useLogout();
  const current = NAV_ITEMS.find(
    (i) => pathname === i.href || pathname.startsWith(`${i.href}/`),
  );

  return (
    <header className="flex h-14 items-center justify-between border-b px-5">
      <h1 className="text-sm font-semibold">{current?.label ?? "PersonaAI"}</h1>
      <DropdownMenu>
        <DropdownMenuTrigger className="rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <Avatar className="h-8 w-8">
            <AvatarFallback className="text-xs">
              {me ? initials(me.name, me.email) : "…"}
            </AvatarFallback>
          </Avatar>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuLabel className="truncate font-normal">
            <div className="font-medium">{me?.name ?? "Your account"}</div>
            <div className="text-xs text-muted-foreground">{me?.email}</div>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => router.push("/settings")}>
            <SettingsIcon className="mr-2 h-4 w-4" />
            Settings
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => logout.mutate()}>
            <LogOut className="mr-2 h-4 w-4" />
            Log out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}
