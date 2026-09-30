import { redirect } from "next/navigation";

export default function Home() {
  // Auth-gated landing comes in M1; for now the app opens on the dashboard.
  redirect("/dashboard");
}
