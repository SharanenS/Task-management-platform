import Link from "next/link";
export default function NotFound() {
  return (
    <main className="error-page">
      <p className="eyebrow">TASKSPACE</p>
      <h1>This page isn’t available.</h1>
      <p>Return to sign in to continue.</p>
      <Link className="primary-button" href="/sign-in">
        Back to sign in
      </Link>
    </main>
  );
}
