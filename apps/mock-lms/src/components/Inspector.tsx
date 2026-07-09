import { api } from "@skills-mobility/contracts";
import type { Assignment, CourseWithActions, Module, Outcome, Rubric, Submission } from "@skills-mobility/contracts";
import { useEffect, useState } from "react";

interface Loaded {
  modules: Module[];
  assignments: Assignment[];
  rubrics: Rubric[];
  submissions: Submission[];
  outcomes: Record<string, Outcome>;
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
        // Resolve each aligned outcome by id (assignment → outcome_id → outcome).
        const ids = [
          ...new Set(assignments.map((a) => a.outcome_id).filter((x): x is string => !!x)),
        ];
        const fetched = await Promise.all(ids.map((id) => api.outcome(id).catch(() => null)));
        const outcomes: Record<string, Outcome> = {};
        fetched.forEach((o) => {
          if (o) outcomes[o.id] = o;
        });
        const submissions = learnerId ? await api.submissions(courseId, learnerId) : [];
        if (live) setData({ modules, assignments, rubrics, submissions, outcomes });
      } catch (e) {
        if (live) setErr(String(e));
      }
    })();
    return () => {
      live = false;
    };
  }, [courseId, learnerId]);

  const learner = course?.learners.find((l) => l.id === learnerId) ?? null;

  function AssignmentBlock({ assignment: a }: { assignment: Assignment }) {
    if (!data) return null;
    const outcome = a.outcome_id ? data.outcomes[a.outcome_id] : undefined;
    const rubric = data.rubrics.find((r) => r.assignment_id === a.id);
    const submission = data.submissions.find((s) => s.assignment_id === a.id);
    return (
      <div className="asg">
        <div className="asg-top">
          <span className="asg-name">{a.name}</span>
          <span className="pill">{a.role}</span>
          <span className="mono dim">{a.points_possible} pts</span>
        </div>
        {a.description && <p className="asg-desc">{a.description}</p>}
        {outcome && (
          <div className="asg-kv">
            <b>Outcome</b>
            <span>
              <span className="mono">{outcome.code}</span> {outcome.display_name || outcome.title}
            </span>
          </div>
        )}
        {rubric && (
          <div className="asg-kv">
            <b>Rubric</b>
            <span>{rubric.criteria.map((c) => `${c.description} (${c.points})`).join(" · ")}</span>
          </div>
        )}
        {learnerId && (
          <div className="asg-kv">
            <b>Submission</b>
            <span>
              {submission ? (
                <>
                  {learner ? `${learner.name} · ${learner.email}` : learnerId} —{" "}
                  {submission.score ?? "—"}{" "}
                  {submission.grade && <span className="pill grade">{submission.grade}</span>}{" "}
                  <span className="mono dim">{submission.workflow_state}</span>
                </>
              ) : (
                <span className="dim">no submission for this learner</span>
              )}
            </span>
          </div>
        )}
      </div>
    );
  }

  const orderedModules = data ? [...data.modules].sort((m1, m2) => m1.position - m2.position) : [];
  const courseLevel = data ? data.assignments.filter((a) => !a.module_id) : [];
  const inModule = (m: Module) => (data ? data.assignments.filter((a) => a.module_id === m.id) : []);

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
              {!learnerId && (
                <div className="sub dim">Pick a learner in the Trigger panel to see submissions.</div>
              )}
            </div>

            {orderedModules.map((m) => (
              <div className="card" key={m.id}>
                <header>
                  <h3>{m.name}</h3>
                  <span className="tag">{inModule(m).length} assignment(s)</span>
                </header>
                <div className="asg-list">
                  {inModule(m).map((a) => (
                    <AssignmentBlock assignment={a} key={a.id} />
                  ))}
                </div>
              </div>
            ))}

            {courseLevel.length > 0 && (
              <div className="card">
                <header>
                  <h3>Course-level</h3>
                  <span className="tag">{courseLevel.length}</span>
                </header>
                <div className="asg-list">
                  {courseLevel.map((a) => (
                    <AssignmentBlock assignment={a} key={a.id} />
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
