"use client";
import { Button, Notice } from "@/components/ui";
export default function ErrorPage({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="state min-h-screen justify-center">
      <h1>Unable to open this page</h1>
      <Notice>
        Something went wrong. Your last action may need to be checked before
        retrying.
      </Notice>
      <Button onClick={reset}>Try again</Button>
    </main>
  );
}
