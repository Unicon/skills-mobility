import { useEffect, useState } from "react";
import { api } from "../api";
import type { Assignment, CourseWithActions, Module, Rubric, Submission } from "../types";

interface Loaded {
  modules: Module[];
  assignments: Assignment[];
  rubrics: Rubric[];
  submissions: Submission[];
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

export function Inspector({
  course,
  learnerId,
}: {
  course: CourseWithActions | null;
  learnerId: string | null;
}) {
  const [data, setData] = useState<Loaded | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const courseId = course?.id ?? null;

  useEffect(() => {
    if (!courseId) return;
    let live = true;
    setData(null);
    setErr(null);
    (async () => {
      try {
        const [modules, assignments, rubrics] = await Promise.all([
          api.modules(courseId),
          api.assignments(courseId),
          api.rubrics(courseId),
        ]);
        const submissions = learnerId ? await api.submissions(courseId, learnerId) : [];
        if (live) setData({ modules, assignments, rubrics, submissions });
      } catch (e) {
        if (live) setErr(String(e));
      }
    })();
    return () => {
      live = false;
    };
  }, [courseId, learnerId]);

  return (
    <section className="col">
      <div className="col-head">
        <span className="eyebrow">Inspector — Canvas-style source data</span>
        {course && <span className="tag mono">{course.course_code}</span>}
      </div>
      <div className="col-body">
        {!course && <div className="empty">Select a course to inspect its source data.</div>}
        {course && err && (
          <div className="empty">
            Couldn’t load data.
            <br />
            {err}
          </div>
        )}
        {course && !data && !err && <Skeleton />}
        {course && data && (
          <>
            <div className="inspect-hero">
              <div className="code">{course.course_code}</div>
              <h2>{course.name}</h2>
              <div className="sub">
                {course.institution || "—"} · {course.term || "—"} ·{" "}
                <b style={{ color: "var(--ink)" }}>
                  {course.kind === "digital_credential" ? "digital credential" : "standard"}
                </b>
              </div>
            </div>

            <div className="card">
              <header>
                <h3>Modules</h3>
                <span className="tag">{data.modules.length}</span>
              </header>
              <div className="rows">
                {data.modules.map((m) => (
                  <div className="row" key={m.id}>
                    <span className="k">{m.name}</span>
                    <span className="v mono">
                      {m.items.map((i) => i.title).join(", ") || "—"}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="card">
              <header>
                <h3>Assignments</h3>
                <span className="tag">{data.assignments.length}</span>
              </header>
              <div className="rows">
                {data.assignments.map((a) => (
                  <div className="row" key={a.id}>
                    <span className="k">{a.role}</span>
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
                <span className="tag">{learnerId ? data.submissions.length : "pick learner"}</span>
              </header>
              <div className="rows">
                {!learnerId && (
                  <div className="row">
                    <span className="k">—</span>
                    <span className="v">Select a learner in the Trigger panel.</span>
                  </div>
                )}
                {data.submissions.map((s) => (
                  <div className="row" key={s.id}>
                    <span className="k mono">{s.assignment_id}</span>
                    <span className="v">
                      {s.score ?? "—"}{" "}
                      {s.grade && <span className="pill grade">{s.grade}</span>}{" "}
                      <span className="mono" style={{ color: "var(--ink-faint)" }}>
                        {s.workflow_state}
                      </span>
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {data.rubrics.length > 0 && (
              <div className="card">
                <header>
                  <h3>Rubrics</h3>
                  <span className="tag">{data.rubrics.length}</span>
                </header>
                <div className="rows">
                  {data.rubrics.flatMap((r) =>
                    r.criteria.map((c) => (
                      <div className="row" key={c.id}>
                        <span className="k">{c.description}</span>
                        <span className="v mono">{c.points} pts</span>
                      </div>
                    )),
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
