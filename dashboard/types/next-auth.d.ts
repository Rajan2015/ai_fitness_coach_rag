import "next-auth";
import "next-auth/jwt";

declare module "next-auth" {
  interface Session {
    user: {
      name?: string | null;
      phoneHash: string;
    };
  }

  interface User {
    phoneHash: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    phoneHash?: string;
  }
}
