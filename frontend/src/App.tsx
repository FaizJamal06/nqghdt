// Layout + routes. Forecast Trust, Buffer Planner and Methodology arrive in M5.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  BrowserRouter,
  Navigate,
  NavLink,
  Route,
  Routes,
  useLocation,
} from "react-router";
import SettingsBar from "./components/SettingsBar";
import DecisionView from "./pages/DecisionView";
import Overview from "./pages/Overview";
import { DEFAULT_DAY } from "./state/settings";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1 } },
});

function Nav() {
  const { search } = useLocation(); // keep global settings when switching page
  const link = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-1 rounded text-sm ${isActive ? "bg-slate-800 text-white" : "text-slate-700 hover:bg-slate-100"}`;
  return (
    <nav className="flex gap-1">
      <NavLink to={{ pathname: "/", search }} end className={link}>
        Overview
      </NavLink>
      <NavLink
        to={{ pathname: `/decision/${DEFAULT_DAY}`, search }}
        className={link}
      >
        Decision View
      </NavLink>
    </nav>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="min-h-screen bg-slate-50 text-slate-900">
          <header className="flex items-center gap-6 border-b bg-white px-6 py-3">
            <span className="font-semibold">WindDesk</span>
            <Nav />
          </header>
          <SettingsBar />
          <main className="mx-auto max-w-6xl p-6">
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route
                path="/decision"
                element={<Navigate to={`/decision/${DEFAULT_DAY}`} replace />}
              />
              <Route path="/decision/:date" element={<DecisionView />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
          <footer className="px-6 py-4 text-xs text-slate-400">
            Data: Elexon BMRS
          </footer>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
