// Shell only. Router, settings bar and pages arrive in M4.
export default function App() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b bg-white px-6 py-3 font-semibold">
        WindDesk
      </header>
      <main className="p-6 text-sm text-slate-600">
        Scaffold. All times UK local.
      </main>
      <footer className="px-6 py-3 text-xs text-slate-400">
        Data: Elexon BMRS
      </footer>
    </div>
  );
}
