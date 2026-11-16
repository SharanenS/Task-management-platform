"use client";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main className="error-page">
      <p className="eyebrow">TASKSPACE</p>
      <h1>Something interrupted your visit.</h1>
      <p>Please try again. If this continues, contact your administrator.</p>
      <button className="primary-button" onClick={reset}>
        Try again
      </button>
      <a href="/sign-in">Back to sign in</a>
    </main>
  );
}
