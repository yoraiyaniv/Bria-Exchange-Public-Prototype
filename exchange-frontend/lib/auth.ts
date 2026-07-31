import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import Google from "next-auth/providers/google";

const API_URL =
  process.env.API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8001";

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
      authorization: {
        url: "https://accounts.google.com/o/oauth2/v2/auth",
        params: { scope: "openid email profile", response_type: "code" },
      },
      token: "https://oauth2.googleapis.com/token",
      userinfo: "https://openidconnect.googleapis.com/v1/userinfo",
      issuer: "https://accounts.google.com",
    }),
    Credentials({
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        const res = await fetch(`${API_URL}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: credentials.email,
            password: credentials.password,
          }),
        });

        if (!res.ok) return null;

        const data = await res.json();
        return {
          id: data.user.id,
          name: data.user.name,
          email: data.user.email,
          role: data.user.role,
          accessToken: data.token,
        };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user, account, profile }) {
      if (account?.provider === "google" && profile) {
        try {
          const res = await fetch(`${API_URL}/auth/google/sync`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              googleId: profile.sub,
              email: profile.email,
              name: profile.name,
              avatar: (profile as { picture?: string }).picture,
            }),
          });
          if (res.ok) {
            const data = await res.json();
            token.accessToken = data.token;
            token.role = data.user.role;
            token.sub = data.user.id;
            token.name = data.user.name;
            token.email = data.user.email;
          }
        } catch (e) {
          console.error("[auth] Google sync failed:", e);
        }
      }

      if (user && account?.provider === "credentials") {
        token.accessToken = (user as { accessToken?: string }).accessToken;
        token.role = (user as { role?: string }).role;
      }

      return token;
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken as string;
      session.user.role = token.role as string;
      return session;
    },
  },
  pages: {
    signIn: "/login",
  },
  session: { strategy: "jwt" },
  trustHost: true,
  // Use non-secure cookies when NEXTAUTH_URL is http (local dev)
  useSecureCookies: process.env.NEXTAUTH_URL?.startsWith("https://") ?? true,
});

declare module "next-auth" {
  interface Session {
    accessToken: string;
    user: {
      id?: string;
      name?: string | null;
      email?: string | null;
      image?: string | null;
      role: string;
    };
  }
}
