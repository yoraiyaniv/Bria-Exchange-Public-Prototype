import "next-auth";
import "next-auth/jwt";

declare module "next-auth" {
  interface Session {
    accessToken: string;
    user: {
      id: string;
      name?: string | null;
      email?: string | null;
      image?: string | null;
      role: string;
      orgId: string;
      orgName: string;
      apiKey: string;
    };
  }

  interface User {
    role?: string;
    orgId?: string;
    orgName?: string;
    apiKey?: string;
    accessToken?: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    role?: string;
    orgId?: string;
    orgName?: string;
    apiKey?: string;
    accessToken?: string;
  }
}
