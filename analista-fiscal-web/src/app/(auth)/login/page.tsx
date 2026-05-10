import type { Metadata } from "next";
import { LoginCard } from "@/components/auth/login-card";

export const metadata: Metadata = {
  title: "Entrar — FiscalAI",
};

export default function LoginPage() {
  return <LoginCard />;
}
