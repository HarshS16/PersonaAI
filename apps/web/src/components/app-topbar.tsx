"use client";

import { usePathname } from "next/navigation";
import { NAV_ITEMS } from "@/lib/nav";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

export function AppTopbar() {
  const pathname = usePathname();
  const current = NAV_ITEMS.find(
    (i) => pathname === i.href || pathname.startsWith(`${i.href}/`),
  );

  return (
    <header className="flex h-14 items-center justify-between border-b px-5">
      <h1 className="text-sm font-semibold">{current?.label ?? "PersonaAI"}</h1>
      <Avatar className="h-8 w-8">
        <AvatarFallback className="text-xs">You</AvatarFallback>
      </Avatar>
    </header>
  );
}
