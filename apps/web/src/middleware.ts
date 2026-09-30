import { NextResponse, type NextRequest } from "next/server";

/**
 * Lightweight gate based on the presence of the refresh cookie. Real validation
 * happens on the API; this only avoids flashing protected pages to logged-out
 * users and bounces logged-in users away from auth pages.
 */
const PROTECTED = [
  "/dashboard",
  "/persona",
  "/sources",
  "/ask",
  "/career",
  "/content",
  "/portfolio",
  "/settings",
];
const AUTH_PAGES = ["/login", "/signup", "/forgot-password"];

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const hasSession = req.cookies.has("pa_refresh");

  const isProtected = PROTECTED.some((p) => pathname === p || pathname.startsWith(`${p}/`));
  const isAuthPage = AUTH_PAGES.some((p) => pathname === p);

  if (isProtected && !hasSession) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }

  if (isAuthPage && hasSession) {
    const url = req.nextUrl.clone();
    url.pathname = "/dashboard";
    url.search = "";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api).*)"],
};
