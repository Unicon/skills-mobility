import { useEffect, useState } from "react";
import { api } from "../api";
import type { Assignment, Course, Outcome, OutcomeResult, Scenario, Submission } from "../types";

interface Loaded {
  course: Course;
  outcome: Outcome | null;
  assignments: Assignment[];
  submissions: Submission[];
  results: OutcomeResult[];
}

function Skeleton() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="skel" style={{ height: 90 }} />
      <div className="skel" style={{ height: 120 }} />
      <div className="skel" style={{ height: 120 }} />
    </div>
  );
}

export function Inspector({ scenario }: { scenario: Scenario | null }) {
  const [data, setData] = useState<Loaded | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const primary = scenario?.events[0];

  useEffect(() => {
    if (!primary) return;
    let live = true;
    setData(null);
    setErr(null);
    (async () => {
      try {
        const [course, assignments, submissions] = await Promise.all([
          api.course(primary.course_id),
          api.assignments(primary.course_id),
          api.submissions(primary.course_id, primary.user_id),
        ]);
        const outcome = primary.outcome_id ? await api.outcome(primary.outcome_id) : null;
        const results = primary.outcome_id
          ? (await api.outcomeResults(primary.course_id, primary.user_id, primary.outcome_id))
              .outcome_results
          : [];
        if (live) setData({ course, outcome, assignments, submissions, results });
      } catch (e) {
        if (live) setErr(String(e));
      }
    })();
    return () => {
      live = false;
    };
  }, [primary?.course_id, primary?.user_id, primary?.outcome_id]);

  return (
    <section className="col">
      <div className="col-head">
        <span className="eyebrow">Inspector — Canvas-style source data</span>
        {primary && <span className="tag mono">course {primary.course_id}</span>}
      </div>
      <div className="col-body">
        {!scenario && <div className="empty">Select a scenario to inspect its source data.</div>}
        {scenario && err && <div className="empty">Couldn’t load data.<br />{err}</div>}
        {scenario && !data && !err && <Skeleton />}
        {data && (
          <>
            <div className="inspect-hero">
              <div className="code">{data.course.course_code}</div>
              <h2>{data.course.name}</h2>
              <div className="sub">
                Learner <b style={{ color: "var(--ink)" }}>{primary?.user_id}</b> · state{" "}
                {data.course.workflow_state}
              </div>
            </div>

            {data.outcome && (
              <div className="card">
                <header>
                  <h3>Outcome (Skill)</h3>
                  <span className="tag mono">{data.outcome.id}</span>
                </header>
                <div className="rows">
                  <div className="row">
                    <span className="k">Title</span>
                    <span className="v">{data.outcome.title}</span>
                  </div>
                  <div className="row">
                    <span className="k">Definition</span>
                    <span className="v">{data.outcome.display_name}</span>
                  </div>
                  <div className="row">
                    <span className="k">Mastery</span>
                    <span className="v mono">
                      {data.outcome.mastery_points} / {data.outcome.points_possible} pts
                    </span>
                  </div>
                  {data.results.map((r) => (
                    <div className="row" key={r.id}>
                      <span className="k">Result</span>
                      <span className="v">
                        {r.score}/{r.possible}{" "}
                        {r.mastery && <span className="pill mastery">● mastered</span>}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="card">
              <header>
                <h3>Assignments</h3>
                <span className="tag">{data.assignments.length}</span>
              </header>
              <div className="rows">
                {data.assignments.map((a) => (
                  <div className="row" key={a.id}>
                    <span className="k">{a.id}</span>
                    <span className="v">
                      {a.name} · {a.points_possible} pts
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="card">
              <header>
                <h3>Submissions</h3>
                <span className="tag">{data.submissions.length}</span>
              </header>
              <div className="rows">
                {data.submissions.map((s) => (
                  <div className="row" key={s.id}>
                    <span className="k">asg {s.assignment_id}</span>
                    <span className="v">
                      {s.score ?? "—"} {s.grade && <span className="pill grade">{s.grade}</span>}{" "}
                      <span className="mono" style={{ color: "var(--ink-faint)" }}>
                        {s.workflow_state}
                      </span>
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
