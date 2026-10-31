import Link from "next/link";
export default function NotFound() {
  return (
    <main className="state min-h-screen justify-center">
      <h1>Page not found</h1>
      <p>This page is not available in SubCadence.</p>
      <Link className="button button-primary" href="/dashboard">
        Return to workspace
      </Link>
    </main>
  );
}
