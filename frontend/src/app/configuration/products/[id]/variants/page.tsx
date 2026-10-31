"use client";
import { useParams } from "next/navigation";
import { Shell } from "@/components/shell";
import { Configuration, variantsDefinition } from "@/components/configuration";
import { Notice } from "@/components/ui";
export default function Page() {
  const { id } = useParams<{ id: string }>();
  return (
    <Shell operatorOnly>
      {Number.isSafeInteger(Number(id)) && Number(id) > 0 ? (
        <Configuration definition={variantsDefinition(Number(id))} />
      ) : (
        <Notice>Invalid product ID.</Notice>
      )}
    </Shell>
  );
}
