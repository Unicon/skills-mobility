import { AnimatePresence } from "framer-motion";
import { useCallback, useEffect, useState } from "react";
import { api, setRole } from "./api";
import { EmissionTimeline } from "./components/EmissionTimeline";
import { EnvelopeModal } from "./components/EnvelopeModal";
import { Header } from "./components/Header";
import { Inspector } from "./components/Inspector";
import { ScenarioRail } from "./components/ScenarioRail";
import { useEmissionStream } from "./hooks/useEmissionStream";
import type { Emission, Role, Scenario } from "./types";
import { copy } from "./util";

export default function App() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [role, setRoleState] = useState<Role>("instructor");
  const [open, setOpen] = useState<Emission | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const { emissions, state, clear } = useEmissionStream();

  useEffect(() => {
    api.scenarios().then((s) => {
      setScenarios(s);
      setActiveId((cur) => cur ?? s[0]?.id ?? null);
    });
  }, []);

  const flash = useCallback((msg: string) => {
    setToast(msg);
    window.setTimeout(() => setToast(null), 1600);
  }, []);

  const onCopy = useCallback(
    (text: string, label: string) => {
      copy(text).then(() => flash(`Copied ${label}`));
    },
    [flash],
  );

  const onRole = (r: Role) => {
    setRoleState(r);
    setRole(r);
  };

  const onRun = async (id: string) => {
    setBusyId(id);
    setActiveId(id);
    try {
      await api.runScenario(id);
    } catch (e) {
      flash(`Run failed: ${e}`);
    } finally {
      setBusyId(null);
    }
  };

  const onReset = async (id: string) => {
    await api.resetScenario(id);
    clear();
    flash("Emission log reset");
  };

  const active = scenarios.find((s) => s.id === activeId) ?? null;

  return (
    <div className="app">
      <Header state={state} count={emissions.length} role={role} onRole={onRole} />
      <div className="cols">
        <ScenarioRail
          scenarios={scenarios}
          activeId={activeId}
          busyId={busyId}
          onSelect={setActiveId}
          onRun={onRun}
          onReset={onReset}
        />
        <Inspector scenario={active} />
        <EmissionTimeline emissions={emissions} onCopy={onCopy} onOpen={setOpen} />
      </div>

      <AnimatePresence>
        {open && <EnvelopeModal emission={open} onClose={() => setOpen(null)} onCopy={onCopy} />}
      </AnimatePresence>

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
