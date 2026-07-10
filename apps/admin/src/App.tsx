import { useState } from "react";
import { ExecutionListView } from "./components/ExecutionListView";
import { WorkflowDetail } from "./components/WorkflowDetail";

export default function App() {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  return (
    <div className="app">
      <header className="topbar">
        <div className="wordmark">
          ADMIN <span>UI</span>
        </div>
      </header>
      <main className="main">
        {selectedId ? (
          <WorkflowDetail executionId={selectedId} onBack={() => setSelectedId(null)} />
        ) : (
          <ExecutionListView onSelect={setSelectedId} />
        )}
      </main>
    </div>
  );
}
