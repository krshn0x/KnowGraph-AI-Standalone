"use client";

export default function ErrorPage({ reset }: { reset: () => void }) {
  return <main className="fatal-error"><h1>Something interrupted the workspace.</h1>
    <p>Your company knowledge is stored safely in FalkorDB.</p>
    <button className="button primary" onClick={reset}>Try again</button></main>;
}
