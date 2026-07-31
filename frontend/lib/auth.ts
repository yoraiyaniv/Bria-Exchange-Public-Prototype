import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import Google from "next-auth/providers/google";

// Server-side URL (used in NextAuth callbacks running on the Node.js server).
// In Docker the Next.js container can't reach "localhost:8001", so allow
// a separate API_URL env var that uses the Docker service name.
const API_URL = process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
      // Hardcode endpoints so NextAuth doesn't need to fetch the OIDC
      // discovery document at runtime (container has no outbound internet).
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
          orgId: data.org.id,
          orgName: data.org.name,
          apiKey: data.org.apiKey,
          accessToken: data.token,
        };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user, account, profile }) {
      // Google sign-in: sync with backend to get our JWT
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
            token.orgId = data.org.id;
            token.orgName = data.org.name;
            token.apiKey = data.org.apiKey;
            token.sub = data.user.id;
            token.name = data.user.name;
            token.email = data.user.email;
          }
        } catch (e) {
          console.error("[auth] Google sync failed:", e);
        }
      }

      // Credentials sign-in
      if (user && account?.provider === "credentials") {
        token.accessToken = (user as { accessToken?: string }).accessToken;
        token.role = (user as { role?: string }).role;
        token.orgId = (user as { orgId?: string }).orgId;
        token.orgName = (user as { orgName?: string }).orgName;
        token.apiKey = (user as { apiKey?: string }).apiKey;
      }

      return token;
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken as string;
      session.user.role = token.role as string;
      session.user.orgId = token.orgId as string;
      session.user.orgName = token.orgName as string;
      session.user.apiKey = token.apiKey as string;
      return session;
    },
  },
  pages: {
    signIn: "/login",
  },
  session: { strategy: "jwt" },
  trustHost: true,
});
