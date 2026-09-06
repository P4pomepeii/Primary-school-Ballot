"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import type {
  Catalogue, ComparisonCell, ComparisonRequest, ComparisonResponse, EvidenceStatus,
  Observation, ObservationSource, Outcome, Priority, Requirement, Topic,
} from "./comparison-types";

const STATUS: Record<EvidenceStatus, string> = {
  supported: "Supported by your information", not_met: "Requirement not met",
  unknown: "Needs confirmation", conflicting: "Conflicting information",
};
const SOURCE: Record<ObservationSource | "demo", string> = {
  school_response: "School response · recorded by you",
  published_information: "Published information · added by you",
  parent_experience: "Parent experience · individual account",
  family_observation: "Your own observation",
  demo: "Fictional demo information",
};
const OUTCOME: Record<Outcome, string> = {
  supports: "Supports the requirement",
  does_not_support: "Does not meet the requirement",
  unclear: "Still unclear",
};
const ASSESSMENT = {
  needs_confirmation: "Requirements to check",
  unmet_requirement: "An unmet must-have",
  requirements_supported: "Must-haves supported by your notes",
  preferences_only: "Preferences to compare",
};
const defaultRequirements: Requirement[] = [
  { id: "quiet-space", topic: "quiet_space", priority: "must_have", details: "", max_minutes: null },
  { id: "student-care", topic: "student_care", priority: "must_have", details: "", max_minutes: null },
  { id: "commute", topic: "commute", priority: "preference", details: "", max_minutes: 20 },
];

function today() {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Singapore", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date());
  return ["year", "month", "day"].map((type) => parts.find((part) => part.type === type)?.value).join("-");
}

function dateLabel(value: string) {
  return new Intl.DateTimeFormat("en-SG", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(`${value}T00:00:00Z`));
}

async function getComparison(request: ComparisonRequest): Promise<ComparisonResponse> {
  const res = await fetch("/api/compare", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request), signal: AbortSignal.timeout(20000),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error ?? "We couldn’t update this comparison. Please try again.");
  return data;
}

function changesBetween(before: ComparisonResponse, after: ComparisonResponse) {
  return after.rows.flatMap((row) => row.cells.flatMap((cell) => {
    const previous = before.rows.find((r) => r.requirement.id === row.requirement.id)?.cells.find((c) => c.school_id === cell.school_id);
    if (!previous || previous.status === cell.status) return [];
    const school = after.schools.find((s) => s.school_id === cell.school_id)?.school_name;
    return [`${school} · ${row.label}: ${STATUS[previous.status]} → ${STATUS[cell.status]}.`];
  }));
}

function EvidenceCell({ cell, busy, onAdd, onRemove }: {
  cell: ComparisonCell; busy: boolean; onAdd: () => void; onRemove: (id: string) => void;
}) {
  return <td>
    <span className={`pill ${cell.status}`}>{STATUS[cell.status]}</span>
    <p className="cell-explanation">{cell.explanation}</p>
    {cell.evidence.length > 0 && <details className="sources">
      <summary>View sources ({cell.evidence.length})</summary>
      {cell.evidence.map((evidence) => <div className="source" key={evidence.id}>
        <div className="source-kind">{SOURCE[evidence.source_type]}</div>
        <small>{evidence.source_label} · {evidence.observed_on ? dateLabel(evidence.observed_on) : "No verification date"}</small>
        <p>{evidence.summary}</p>
        {!evidence.is_demo && <p className="help">{evidence.commute_minutes != null ? "Journey assessment" : "Your assessment"}: {OUTCOME[evidence.outcome]}</p>}
        {evidence.commute_minutes != null && <p>{evidence.commute_minutes} minutes recorded</p>}
        {evidence.source_url && <p><a href={evidence.source_url} target="_blank" rel="noopener noreferrer">Open source ↗</a></p>}
        {!evidence.is_demo && <button type="button" className="text-button danger" disabled={busy} onClick={() => onRemove(evidence.id)}>Remove this note</button>}
      </div>)}
    </details>}
    <button type="button" className="text-button" disabled={busy} onClick={onAdd}>+ Record what you learned</button>
  </td>;
}

function ObservationForm({ schoolName, requirement, label, busy, onSave, onCancel }: {
  schoolName: string; requirement: Requirement; label: string; busy: boolean;
  onSave: (value: Omit<Observation, "id" | "school_id" | "requirement_id">) => Promise<void>;
  onCancel: () => void;
}) {
  const [sourceType, setSourceType] = useState<ObservationSource>("school_response");
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => { headingRef.current?.focus(); }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const data = new FormData(event.currentTarget);
    const minutes = String(data.get("commute_minutes") ?? "");
    await onSave({
      source_type: sourceType,
      source_label: String(data.get("source_label") ?? "").trim(),
      source_url: String(data.get("source_url") ?? "").trim() || null,
      observed_on: String(data.get("observed_on")),
      summary: String(data.get("summary") ?? "").trim(),
      outcome: String(data.get("outcome")) as Outcome,
      commute_minutes: minutes ? Number(minutes) : null,
    });
  }
  return <section className="panel note-panel" id="record-information" aria-labelledby="note-title">
    <div className="note-heading">
      <div>
        <p className="eyebrow">{schoolName} · {label}</p>
        <h2 id="note-title" tabIndex={-1} ref={headingRef}>Record what you learned</h2>
      </div>
      <button type="button" className="text-button" onClick={onCancel} disabled={busy}>Cancel</button>
    </div>
    {requirement.details && <p className="help">Your requirement: {requirement.details}</p>}
    <p className="help">This information is recorded by you and is not independently verified. Include the circumstances that matter to your child.</p>
    <form onSubmit={submit}>
      <fieldset disabled={busy}>
        <div className="field-pair">
          <label>Where did the information come from?
            <select name="source_type" value={sourceType} onChange={(e) => setSourceType(e.target.value as ObservationSource)}>
              <option value="school_response">A response from the school</option>
              <option value="published_information">A published source</option>
              <option value="parent_experience">Another parent’s experience</option>
              <option value="family_observation">Something our family observed</option>
            </select>
          </label>
          <label>Date of the information
            <input name="observed_on" type="date" required max={today()} defaultValue={today()} />
          </label>
        </div>
        {sourceType === "parent_experience" && <p className="notice">An individual experience adds context. It does not establish that your family’s requirement is met or unmet.</p>}
        <div className="field-pair">
          <label>Source or context
            <input name="source_label" required maxLength={200} placeholder="e.g. School office, open-house conversation" />
          </label>
          <label>Source link {sourceType !== "published_information" && "(optional)"}
            <input name="source_url" type="url" pattern="https?://.*" maxLength={2000} required={sourceType === "published_information"} placeholder="https://…" />
          </label>
        </div>
        <label>What did you learn?
          <textarea name="summary" required maxLength={2000} rows={3} placeholder="Record the response or observation, including any conditions or limits." />
        </label>
        {requirement.topic === "commute" ? <>
          <label>Door-to-door travel time in minutes (optional)
            <input name="commute_minutes" type="number" min={1} max={300} step={1} placeholder="e.g. 18" />
          </label>
          <input name="outcome" type="hidden" value="unclear" />
          <p className="help">Compared with your {requirement.max_minutes}-minute limit. Without a recorded time, the journey remains unconfirmed.</p>
        </> : <label>How does this relate to your requirement?
          <select name="outcome" required defaultValue="unclear">
            <option value="unclear">It is still unclear</option>
            <option value="supports">It supports this requirement</option>
            <option value="does_not_support">It shows this requirement is not met</option>
          </select>
        </label>}
        <div className="actions">
          <button className="primary" type="submit" disabled={busy}>{busy ? "Updating comparison…" : "Save note & update comparison"}</button>
        </div>
      </fieldset>
    </form>
  </section>;
}

export default function HomePage() {
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null);
  const [catalogueError, setCatalogueError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [schoolIds, setSchoolIds] = useState<[string, string]>(["", ""]);
  const [context, setContext] = useState("");
  const [requirements, setRequirements] = useState<Requirement[]>(defaultRequirements);
  const [comparison, setComparison] = useState<ComparisonResponse | null>(null);
  const [activeRequest, setActiveRequest] = useState<ComparisonRequest | null>(null);
  const [editing, setEditing] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [changes, setChanges] = useState<string[] | null>(null);
  const [noteTarget, setNoteTarget] = useState<{ schoolId: string; requirementId: string } | null>(null);
  const resultHeading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);
    let disposed = false;
    setCatalogueError(null);
    async function load() {
      try {
        const response = await fetch("/api/schools", { cache: "no-store", signal: controller.signal });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error ?? "We couldn’t load the schools.");
        if (!disposed) {
          setCatalogue(data);
          setSchoolIds((current) => current[0] ? current : [data.schools[0]?.school_id ?? "", data.schools[2]?.school_id ?? data.schools[1]?.school_id ?? ""]);
        }
      } catch (err) {
        if (!disposed) setCatalogueError(err instanceof Error && err.name !== "AbortError" ? err.message : "Loading the schools took too long. Please try again.");
      } finally { clearTimeout(timeout); }
    }
    void load();
    return () => { disposed = true; clearTimeout(timeout); controller.abort(); };
  }, [retry]);

  useEffect(() => {
    if (!editing && comparison && !noteTarget) resultHeading.current?.focus();
  }, [editing, comparison, noteTarget]);

  function toggleTopic(topic: Topic) {
    setRequirements((current) => current.some((r) => r.topic === topic)
      ? current.filter((r) => r.topic !== topic)
      : [...current, { id: crypto.randomUUID(), topic, priority: "preference", details: "", max_minutes: topic === "commute" ? 20 : null }]);
  }
  function editRequirement(id: string, update: Partial<Requirement>) {
    // Notes assess a specific requirement. Changing its meaning creates a new identity;
    // changing only its priority leaves the supporting evidence applicable.
    setRequirements((current) => current.map((r) => r.id === id
      ? { ...r, ...update, id: "details" in update || "max_minutes" in update ? crypto.randomUUID() : r.id }
      : r));
  }
  async function submitComparison(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || schoolIds[0] === schoolIds[1] || !requirements.length) return;
    setBusy(true); setError(null);
    const request: ComparisonRequest = {
      school_ids: schoolIds, context: context.trim(), requirements,
      observations: (activeRequest?.observations ?? []).filter((note) => schoolIds.includes(note.school_id) && requirements.some((r) => r.id === note.requirement_id)),
    };
    try {
      const result = await getComparison(request);
      setComparison(result); setActiveRequest(request); setEditing(false); setChanges(null); setNoteTarget(null);
    } catch (err) { setError(err instanceof Error ? err.message : "We couldn’t compare these schools."); }
    finally { setBusy(false); }
  }
  function beginEdit() {
    if (!activeRequest) return;
    setSchoolIds(activeRequest.school_ids); setContext(activeRequest.context); setRequirements(activeRequest.requirements);
    setEditing(true); setNoteTarget(null); setError(null);
  }
  async function updateNotes(notes: Observation[]) {
    if (!activeRequest || !comparison || busy) return false;
    setBusy(true); setError(null);
    const request = { ...activeRequest, observations: notes };
    try {
      const result = await getComparison(request);
      setChanges(changesBetween(comparison, result));
      setComparison(result); setActiveRequest(request); setNoteTarget(null);
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Your update wasn’t saved. Please try again.");
      return false;
    } finally { setBusy(false); }
  }
  function addNote(schoolId: string, requirementId: string) {
    setError(null); setNoteTarget({ schoolId, requirementId });
  }
  const targetRow = comparison?.rows.find((row) => row.requirement.id === noteTarget?.requirementId);
  const targetSchool = comparison?.schools.find((school) => school.school_id === noteTarget?.schoolId);
  const excludedNotes = (activeRequest?.observations ?? []).filter((note) => !schoolIds.includes(note.school_id) || !requirements.some((r) => r.id === note.requirement_id)).length;

  return <main className="shell">
    <header className="topbar">
      <a href="/" className="wordmark">School-Fit Copilot</a>
      <nav aria-label="Main navigation">
        <a href="/" aria-current="page">Compare</a>
        <a href="/discover">Discovery demo</a>
      </nav>
    </header>

    {editing && <div className="intro">
      <h1>Two schools. Your family’s priorities.</h1>
      <p>Compare what matters, see what needs checking, and keep track of what you learn.</p>
    </div>}
    <aside className="notice" style={!editing ? { marginTop: 24 } : undefined}>
      <strong>Demo workspace</strong>
      {catalogue?.notice ?? "All five school records are fictional. Use this workspace to explore the comparison process."}
    </aside>

    {!catalogue && <div className="panel empty" role="status">
      {catalogueError ? <><p>{catalogueError}</p><button className="secondary" onClick={() => setRetry((n) => n + 1)}>Retry loading schools</button></> : "Loading schools and priorities…"}
    </div>}

    {catalogue && editing && <form onSubmit={submitComparison}>
      <fieldset disabled={busy}>
        <section className="panel" aria-labelledby="schools-title">
          <div className="section-heading">
            <span className="step" aria-hidden="true">1</span>
            <div><h2 id="schools-title">Choose two schools to compare</h2><p className="help">For a real decision, first check that both schools are realistic registration options.</p></div>
          </div>
          <div className="school-pickers">
            {([0, 1] as const).map((index) => <div className="school-picker" key={index}>
              <label>School {index === 0 ? "A" : "B"}
                <select required value={schoolIds[index]} onChange={(e) => setSchoolIds((current) => index === 0 ? [e.target.value, current[1]] : [current[0], e.target.value])}>
                  <option value="" disabled>Select a school</option>
                  {catalogue.schools.map((school) => <option value={school.school_id} key={school.school_id}>{school.school_name}</option>)}
                </select>
              </label>
            </div>)}
          </div>
          {schoolIds[0] === schoolIds[1] && <p className="error" role="alert">Choose two different schools.</p>}
          <label htmlFor="family-context">What is keeping you undecided? <span className="help">(optional)</span></label>
          <textarea id="family-context" value={context} maxLength={3000} onChange={(e) => setContext(e.target.value)} placeholder="e.g. Our child gets overwhelmed by noise, and we need care after school. We’re unsure how either school handles this." rows={3} style={{ marginTop: 8 }} />
          <p className="help" style={{ margin: "8px 0 0" }}>Use the priorities below to turn your concern into specific requirements. Your notes stay in this page session.</p>
        </section>

        <section className="panel" aria-labelledby="priorities-title">
          <div className="section-heading">
            <span className="step" aria-hidden="true">2</span>
            <div><h2 id="priorities-title">Decide what matters to your family</h2><p className="help">Must-haves are checked individually. Preferences cannot offset an unmet requirement.</p></div>
          </div>
          <div className="topics">
            {catalogue.topics.map((topic) => {
              const requirement = requirements.find((r) => r.topic === topic.id);
              return <div key={topic.id} className={`topic ${requirement ? "selected" : ""}`}>
                <label className="topic-toggle">
                  <input type="checkbox" checked={Boolean(requirement)} onChange={() => toggleTopic(topic.id)} />
                  <span>{topic.label}<span className="help">{topic.description}</span></span>
                </label>
                {requirement && <div className="topic-controls">
                  <label>Importance for {topic.label.toLowerCase()}
                    <select value={requirement.priority} onChange={(e) => editRequirement(requirement.id, { priority: e.target.value as Priority })}>
                      <option value="must_have">Must-have</option><option value="preference">Preference</option>
                    </select>
                  </label>
                  {topic.id === "commute" && <label>Maximum door-to-door journey (minutes)
                    <input type="number" required min={1} max={180} step={1} value={requirement.max_minutes ?? ""} onChange={(e) => editRequirement(requirement.id, { max_minutes: e.target.value ? Number(e.target.value) : null })} />
                  </label>}
                  <label>What would meet this need? {topic.id !== "custom" && <span className="help">(optional)</span>}
                    <textarea rows={2} maxLength={500} required={topic.id === "custom"} value={requirement.details} onChange={(e) => editRequirement(requirement.id, { details: e.target.value })} placeholder={topic.id === "student_care" ? "e.g. A confirmed place until 6pm on weekdays" : topic.id === "quiet_space" ? "e.g. A quiet space our child can access when overwhelmed" : "Describe the arrangement that would work for your child."} />
                  </label>
                </div>}
              </div>;
            })}
          </div>
        </section>
        {error && <p className="error" role="alert">{error}</p>}
        {excludedNotes > 0 && <p className="notice">{excludedNotes} note(s) belong to a removed school or changed requirement and will be excluded when you update. Cancel to keep the current comparison.</p>}
        <div className="actions">
          <button type="submit" className="primary" disabled={busy || !requirements.length || !schoolIds[0] || !schoolIds[1] || schoolIds[0] === schoolIds[1]}>{busy ? "Comparing…" : comparison ? "Update schools & priorities" : "Compare these schools"}</button>
          {comparison && <button type="button" className="secondary" onClick={() => { setEditing(false); setError(null); }}>Cancel edits</button>}
          <span className="help">{requirements.length ? `${requirements.length} priorities selected` : "Select at least one priority."}</span>
        </div>
      </fieldset>
    </form>}

    {!editing && comparison && <>
      <div className="workspace-heading">
        <h1 tabIndex={-1} ref={resultHeading}>Your comparison</h1>
        <button type="button" className="secondary" disabled={busy || noteTarget !== null} onClick={beginEdit}>Edit schools & priorities</button>
      </div>
      {comparison.context && <div className="context"><p className="eyebrow">Your deciding concern</p><p>{comparison.context}</p></div>}
      {changes !== null && <div className="changes" role="status">
        <strong>Comparison updated</strong>
        {changes.length ? <ul>{changes.map((change) => <li key={change}>{change}</li>)}</ul> : <p style={{ margin: "6px 0 0" }}>Your evidence changed. The requirement statuses remain the same.</p>}
      </div>}
      <div className="assessment-grid">
        {comparison.assessments.map((assessment, index) => <article className={`assessment ${assessment.state}`} key={assessment.school_id}>
          <p className="eyebrow" style={{ margin: "0 0 8px" }}>School {index === 0 ? "A" : "B"} · fictional record</p>
          <h2>{comparison.schools.find((s) => s.school_id === assessment.school_id)?.school_name}</h2>
          <span className={`pill ${assessment.state === "unmet_requirement" ? "not_met" : assessment.state === "requirements_supported" ? "supported" : "unknown"}`}>{ASSESSMENT[assessment.state]}</span>
          <p>{assessment.summary}</p>
        </article>)}
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      {noteTarget && targetRow && targetSchool && <ObservationForm
        key={`${noteTarget.schoolId}:${noteTarget.requirementId}`}
        schoolName={targetSchool.school_name} requirement={targetRow.requirement} label={targetRow.label} busy={busy}
        onCancel={() => { setNoteTarget(null); setError(null); }}
        onSave={async (value) => { await updateNotes([...(activeRequest?.observations ?? []), { ...value, id: crypto.randomUUID(), school_id: noteTarget.schoolId, requirement_id: noteTarget.requirementId }]); }}
      />}
      <section className="panel table-panel" aria-labelledby="evidence-title">
        <div className="table-heading"><h2 id="evidence-title">What the evidence tells you</h2><p className="help">Read each requirement separately. Missing information means there is something to check.</p></div>
        <div className="table-scroll" role="region" aria-label="School comparison; scroll horizontally on smaller screens" tabIndex={0}>
          <table className="comparison-table">
            <caption className="sr-only">Two schools compared against your requirements, with source details and questions.</caption>
            <thead><tr><th scope="col">Your priorities</th>{comparison.schools.map((school) => <th scope="col" key={school.school_id}>{school.school_name}</th>)}</tr></thead>
            <tbody>{comparison.rows.map((row) => <tr key={row.requirement.id}>
              <th scope="row"><h3>{row.label}</h3><span className={`pill ${row.requirement.priority === "must_have" ? "required" : "preference"}`}>{row.requirement.priority === "must_have" ? "Must-have" : "Preference"}</span>
                {row.requirement.topic === "commute" && <p className="requirement-details">Up to {row.requirement.max_minutes} minutes door-to-door</p>}
                {row.requirement.details && <p className="requirement-details">{row.requirement.details}</p>}
              </th>
              {row.cells.map((cell) => <EvidenceCell cell={cell} key={cell.school_id} busy={busy || noteTarget !== null}
                onAdd={() => addNote(cell.school_id, row.requirement.id)}
                onRemove={(id) => { void updateNotes((activeRequest?.observations ?? []).filter((note) => note.id !== id)); }} />)}
            </tr>)}</tbody>
          </table>
        </div>
      </section>
      <section className="panel" aria-labelledby="questions-title">
        <div className="section-heading"><span className="step" aria-hidden="true">3</span><div><h2 id="questions-title">What to check next</h2><p className="help">Start with your must-haves. Record the answers to update this comparison.</p></div></div>
        {comparison.questions.length === 0 ? <p>There are no unresolved requirements in your recorded information. Revisit the comparison if arrangements change.</p> : <ol className="next-questions">
          {comparison.questions.map((question) => <li key={question.id}>
            <div><span className="question-label">{comparison.schools.find((s) => s.school_id === question.school_id)?.school_name} · {question.priority === "must_have" ? "Must-have" : "Preference"}</span><p>{question.question}</p><p className="help">{question.reason}</p></div>
            <button type="button" className="secondary" disabled={busy || noteTarget !== null} onClick={() => addNote(question.school_id, question.requirement_id)}>Record an answer</button>
          </li>)}
        </ol>}
      </section>
      <p className="session-note">{activeRequest?.observations.length ?? 0} notes in this session. Refreshing or leaving this page clears your comparison. The comparison checks your recorded requirements; it does not predict admission or your child’s future experience.</p>
    </>}
  </main>;
}
