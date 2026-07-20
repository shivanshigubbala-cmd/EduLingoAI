import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const protectedRoutes = ["/dashboard", "/chat", "/quiz", "/schedule", "/upload"];

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const isProtected = protectedRoutes.some(
    (route) => pathname === route || pathname.startsWith(route + "/"),
  );

  if (!isProtected) {
    return NextResponse.next();
  }

  const cookieHeader = request.headers.get("cookie") ?? "";

  try {
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: { cookie: cookieHeader },
    });

    if (res.ok) {
      return NextResponse.next();
    }
  } catch {
    // Backend unreachable — fall through to redirect
  }

  const loginUrl = new URL("/login", request.url);
  loginUrl.searchParams.set("next", pathname);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/chat/:path*",
    "/quiz/:path*",
    "/schedule/:path*",
    "/upload/:path*",
  ],
};
