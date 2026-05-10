import { redirect } from "next/navigation";

export default function FolhaIndexPage() {
  const hoje = new Date();
  redirect(`/pessoal/folha/${hoje.getFullYear()}/${hoje.getMonth() + 1}`);
}
