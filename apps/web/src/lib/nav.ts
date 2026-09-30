import {
  LayoutDashboard,
  User,
  Plug,
  MessagesSquare,
  Briefcase,
  PenLine,
  Globe,
  Settings,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
};

/** Primary navigation, per SRD §50. */
export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Persona", href: "/persona", icon: User },
  { label: "Sources", href: "/sources", icon: Plug },
  { label: "Ask AI", href: "/ask", icon: MessagesSquare },
  { label: "Career", href: "/career", icon: Briefcase },
  { label: "Content", href: "/content", icon: PenLine },
  { label: "Portfolio", href: "/portfolio", icon: Globe },
  { label: "Settings", href: "/settings", icon: Settings },
];
