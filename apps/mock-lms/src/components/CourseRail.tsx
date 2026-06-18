import type { CourseWithActions } from "../types";

const KIND_LABEL: Record<string, string> = {
  standard: "standard",
  digital_credential: "digital credential",
};

export function CourseRail({
  courses,
  activeId,
  onSelect,
}: {
  courses: CourseWithActions[];
  activeId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <section className="col">
      <div className="col-head">
        <span className="eyebrow">Courses</span>
        <span className="tag">{courses.length}</span>
      </div>
      <div className="col-body">
        {courses.map((c) => (
          <button
            key={c.id}
            className={`scenario ${c.id === activeId ? "active" : ""}`}
            onClick={() => onSelect(c.id)}
          >
            <h4>{c.name}</h4>
            <p>
              {c.institution || "—"} · {c.term || "—"}
            </p>
            <div className="meta">
              <span className="tag mono">{c.course_code}</span>
              <span className="tag">{KIND_LABEL[c.kind] ?? c.kind}</span>
              <span className="tag">{c.actions.length} actions</span>
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}
