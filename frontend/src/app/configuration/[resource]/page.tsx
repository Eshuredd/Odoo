"use client";
import { useParams } from "next/navigation";
import { Shell } from "@/components/shell";
import { Configuration, definitions } from "@/components/configuration";
import { Notice } from "@/components/ui";
export default function Page() {
  const { resource } = useParams<{ resource: string }>();
  const definition = definitions[resource];
  return (
    <Shell operatorOnly>
      {definition ? (
        <Configuration key={resource} definition={definition} />
      ) : (
        <Notice>Configuration page not found.</Notice>
      )}
    </Shell>
  );
}
