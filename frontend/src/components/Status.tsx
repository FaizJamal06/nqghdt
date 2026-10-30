// Loading skeleton, error state with retry, empty state (PRD §9 UI rules).

export function Skeleton({ className = "h-64" }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-slate-200 ${className}`} />;
}

export function ErrorState({
  error,
  retry,
}: {
  error: Error;
  retry: () => void;
}) {
  return (
    <div className="rounded border border-red-200 bg-red-50 p-4 text-sm text-red-800">
      <p>Couldn't load data: {error.message}</p>
      <button className="mt-2 underline" onClick={retry}>
        Try again
      </button>
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
      {children}
    </div>
  );
}
