"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { isLogado } from "@/lib/auth";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import { LoadingState } from "@/components/shared/loading-state";
import { useOnboardingStore } from "@/lib/stores/onboarding-store";
import { WizardShell } from "@/components/onboarding/wizard-shell";
import { PassoCnpj } from "@/components/onboarding/passo-cnpj";
import { PassoRegime } from "@/components/onboarding/passo-regime";
import { PassoCertificado } from "@/components/onboarding/passo-certificado";
import { PassoBancos } from "@/components/onboarding/passo-bancos";
import { PassoConclusao } from "@/components/onboarding/passo-conclusao";

export default function OnboardingPage() {
  const router = useRouter();
  const { empresa, loading } = useEmpresaAtual();
  const passo = useOnboardingStore((s) => s.passo);
  const [verificado, setVerificado] = React.useState(false);

  React.useEffect(() => {
    if (loading) return;
    if (!isLogado()) {
      router.replace("/login");
      return;
    }
    if (empresa) {
      router.replace("/home");
      return;
    }
    setVerificado(true);
  }, [loading, empresa, router]);

  if (loading || !verificado) {
    return <LoadingState titulo="Preparando seu cadastro..." />;
  }

  return (
    <WizardShell>
      {passo === 1 ? <PassoCnpj /> : null}
      {passo === 2 ? <PassoRegime /> : null}
      {passo === 3 ? <PassoCertificado /> : null}
      {passo === 4 ? <PassoBancos /> : null}
      {passo === 5 ? <PassoConclusao /> : null}
    </WizardShell>
  );
}
