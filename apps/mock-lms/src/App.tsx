import { api } from "@skills-mobility/contracts";
import type { ActionView, CourseWithActions, EventEnvelope, RunResult, Scope } from "@skills-mobility/contracts";
import { EnvelopeModal } from "@skills-mobility/ui";
import { AnimatePresence } from "motion/react";
import { useCallback, useEffect, useState } from "react";
import { CourseRail } from "./components/CourseRail";
import { Header } from "./components/Header";
import { Inspector } from "./components/Inspector";
import { TriggerPanel } from "./components/TriggerPanel";
import { copy } from "./util";

export default function App() {
  const [courses, setCourses] = useState<CourseWithActions[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [scope, setScope] = useState<Scope>("one");
  const [learnerId, setLearnerId] = useState<string | null>(null);
  const [busyActionId, setBusyActionId] = useState<string | null>(null);
  const [lastRun, setLastRun] = useState<RunResult | null>(null);
  const [open, setOpen] = useState<EventEnvelope | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    api.courses().then((cs) => {
      setCourses(cs);
      setActiveId((cur) => cur ?? cs[0]?.id ?? null);
    });
  }, []);

  const active = courses.find((c) => c.id === activeId) ?? null;

  // Default the learner selection to the active course's first learner.
  useEffect(() => {
    setLearnerId(active?.learners[0]?.id ?? null);
    setLastRun(null);
  }, [activeId]); // eslint-disable-line react-hooks/exhaustive-deps

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

  const onRun = async (action: ActionView) => {
    if (!active) return;
    setBusyActionId(action.id);
    try {
      const result = await api.runAction(
        active.id,
        action.id,
        scope,
        scope === "one" ? (learnerId ?? undefined) : undefined,
      );
      setLastRun(result);
      flash(`Emitted ${result.emitted.length} event(s)`);
    } catch (e) {
      flash(`Run failed: ${e}`);
    } finally {
      setBusyActionId(null);
    }
  };

  return (
    <div className="app">
      <Header />
      <div className="cols">
        <CourseRail courses={courses} activeId={activeId} onSelect={setActiveId} />
        <Inspector course={active} learnerId={learnerId} />
        <TriggerPanel
          course={active}
          scope={scope}
          onScope={setScope}
          learnerId={learnerId}
          onLearner={setLearnerId}
          busyActionId={busyActionId}
          onRun={onRun}
          lastRun={lastRun}
          onOpenEnvelope={setOpen}
          onCopy={onCopy}
        />
      </div>

      <AnimatePresence>
        {open && (
          <EnvelopeModal envelope={open} onClose={() => setOpen(null)} onCopy={onCopy} />
        )}
      </AnimatePresence>

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
