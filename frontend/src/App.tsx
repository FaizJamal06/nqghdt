// Layout + routes (PRD §9 paths). Global settings bar sits under the nav on every page.
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
import BufferPlanner from "./pages/BufferPlanner";
import DecisionView from "./pages/DecisionView";
import ForecastTrust from "./pages/ForecastTrust";
import Methodology from "./pages/Methodology";
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
    <nav className="flex flex-wrap gap-1">
      <NavLink to={{ pathname: "/", search }} end className={link}>
        Overview
      </NavLink>
      <NavLink
        to={{ pathname: `/decision/${DEFAULT_DAY}`, search }}
        className={link}
      >
        Decision View
      </NavLink>
      <NavLink to={{ pathname: "/accuracy", search }} className={link}>
        Forecast Trust
      </NavLink>
      <NavLink to={{ pathname: "/planner", search }} className={link}>
        Buffer Planner
      </NavLink>
      <NavLink to={{ pathname: "/methodology", search }} className={link}>
        Methodology
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
              <Route path="/accuracy" element={<ForecastTrust />} />
              <Route path="/planner" element={<BufferPlanner />} />
              <Route path="/methodology" element={<Methodology />} />
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
