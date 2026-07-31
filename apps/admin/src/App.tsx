import { ThemeToggle } from "@skills-mobility/ui";
import { Route, Routes, useNavigate, useParams } from "react-router-dom";
import { ExecutionListView } from "./components/ExecutionListView";

import { WorkflowDetail } from "./components/WorkflowDetail";

function ListRoute() {
  const navigate = useNavigate();
  return <ExecutionListView onSelect={(executionId) => navigate(`/executions/${executionId}`)} />;
}

function DetailRoute() {
  // Non-null: the route only matches with a non-empty :executionId segment.
  const { executionId } = useParams<{ executionId: string }>();
  const navigate = useNavigate();
  return <WorkflowDetail executionId={executionId!} onBack={() => navigate("/")} />;
}

export default function App() {
  return (
    <div className="app">
      <header className="topbar">
        <div className="wordmark">
          ADMIN <span>UI</span>
        </div>
        <ThemeToggle storageKey="admin-theme" />
      </header>
      <main className="main">
        <Routes>
          <Route path="/" element={<ListRoute />} />
          <Route path="/executions/:executionId" element={<DetailRoute />} />
        </Routes>
      </main>
    </div>
  );
}
