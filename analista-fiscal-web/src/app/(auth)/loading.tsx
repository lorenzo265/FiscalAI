import { LoadingState } from "@/components/shared/loading-state";

export default function AuthLoading() {
  return (
    <div className="min-h-[60vh] grid place-items-center">
      <LoadingState titulo="Carregando..." />
    </div>
  );
}
