import type { CSSProperties } from "react";
import type { ActionView, CourseWithActions, EventEnvelope, RunResult, Scope } from "../types";
import { eventColor, shortId } from "../util";

export function TriggerPanel({
  course,
  scope,
  onScope,
  learnerId,
  onLearner,
  busyActionId,
  onRun,
  lastRun,
  onOpenEnvelope,
  onCopy,
}: {
  course: CourseWithActions | null;
  scope: Scope;
  onScope: (s: Scope) => void;
  learnerId: string | null;
  onLearner: (id: string) => void;
  busyActionId: string | null;
  onRun: (action: ActionView) => void;
  lastRun: RunResult | null;
  onOpenEnvelope: (env: EventEnvelope) => void;
  onCopy: (text: string, label: string) => void;
}) {
  const runAction =
    course && lastRun ? course.actions.find((a) => a.id === lastRun.action_id) : null;
  const runColor = eventColor(runAction?.event_type ?? "");

  return (
    <section className="col">
      <div className="col-head">
        <span className="eyebrow">Trigger & Confirm</span>
      </div>
      <div className="col-body">
        {!course && <div className="empty">Select a course to see its grading Actions.</div>}

        {course && (
          <>
            <div className="card">
              <header>
                <h3>Scope</h3>
                <div className="role-toggle">
                  {(["one", "all"] as Scope[]).map((s) => (
                    <button key={s} className={scope === s ? "on" : ""} onClick={() => onScope(s)}>
                      {s === "one" ? "one learner" : "all learners"}
                    </button>
                  ))}
                </div>
              </header>
              {scope === "one" && (
                <div className="rows">
                  <div className="row">
                    <span className="k">Learner</span>
                    <span className="v">
                      <select
                        className="select"
                        value={learnerId ?? ""}
                        onChange={(e) => onLearner(e.target.value)}
                      >
                        {course.learners.map((l) => (
                          <option key={l.id} value={l.id}>
                            {l.name} ({l.email})
                          </option>
                        ))}
                      </select>
                    </span>
                  </div>
                </div>
              )}
            </div>

            {course.actions.map((a) => {
              const color = a.event_type ? eventColor(a.event_type) : "var(--ink-faint)";
              const busy = busyActionId === a.id;
              return (
                <div className="card" key={a.id}>
                  <header>
                    <h3>{a.label}</h3>
                    <span className="tag mono" style={{ color }}>
                      {a.event_type}
                    </span>
                  </header>
                  <div className="rows">
                    <div className="row">
                      <span className="k">Grades</span>
                      <span className="v">{a.assignment_name ?? a.assignment_id}</span>
                    </div>
                    <div className="btn-row">
                      <button
                        className="btn primary"
                        disabled={busy || (scope === "one" && !learnerId)}
                        onClick={() => onRun(a)}
                      >
                        {busy ? "Emitting…" : `Grade → emit ${a.event_type}`}
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}

            {lastRun && (
              <div className="card" style={{ borderColor: "rgba(230,180,80,0.4)" }}>
                <header>
                  <h3>Emitted</h3>
                  <span
                    className="tag mono copyable"
                    title="Copy correlation id"
                    onClick={() => onCopy(lastRun.correlation_id, "correlation id")}
                  >
                    {shortId(lastRun.correlation_id)}
                  </span>
                </header>
                <div className="rows">
                  <div className="timeline">
                    {lastRun.emitted.map((env) => (
                      <button
                        key={env.metadata.event_id}
                        className="emission"
                        style={{ "--type-color": runColor } as CSSProperties}
                        onClick={() => onOpenEnvelope(env)}
                      >
                        <div className="e-top">
                          <span className="e-name">{env.metadata.event_name}</span>
                          <span className="e-time">{shortId(env.metadata.event_id)}</span>
                        </div>
                        <div className="e-meta">
                          <span className="kv">
                            <b>user</b> {env.metadata.user_id}
                          </span>
                          <span className="kv">
                            <b>action</b> {env.metadata.action_id}
                          </span>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
