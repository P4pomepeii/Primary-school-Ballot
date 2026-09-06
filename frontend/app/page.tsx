"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { Fraunces } from "next/font/google";
import styles from "./page.module.css";
import type {
  Catalogue, ComparisonCell, ComparisonRequest, ComparisonResponse, EvidenceStatus,
  Observation, ObservationSource, Outcome, Priority, Requirement, Topic,
} from "./comparison-types";

type Importance = "not_needed" | Priority;

const fraunces = Fraunces({ subsets: ["latin"], weight: ["600", "700"], variable: "--font-fraunces", display: "swap" });

const STATUS: Record<EvidenceStatus, string> = {
  supported: "Supported by your information", not_met: "Requirement not met",
  unknown: "Needs confirmation", conflicting: "Conflicting information",
};
const STATUS_BADGE: Record<EvidenceStatus, string> = {
  supported: "badgeMeets", not_met: "badgeMissing", unknown: "badgeUnclear", conflicting: "badgePartial",
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
const ASSESSMENT_BADGE: Record<keyof typeof ASSESSMENT, string> = {
  needs_confirmation: "badgeUnclear", unmet_requirement: "badgeMissing",
  requirements_supported: "badgeMeets", preferences_only: "badgeUnclear",
};
const NOTE_PLACEHOLDER: Partial<Record<Topic, string>> = {
  student_care: "e.g. A confirmed place until 6pm on weekdays",
  quiet_space: "e.g. A quiet space our child can access when overwhelmed",
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
  const formatter = new Intl.DateTimeFormat("en-SG", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
  return formatter.format(new Date(`${value}T00:00:00Z`));
}

function schoolIdFor(name: string, index: number) {
  const slug = name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 48);
  return `school-${index + 1}-${slug}`;
}

async function getComparison(request: ComparisonRequest): Promise<ComparisonResponse> {
  const res = await fetch("/api/compare", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request), signal: AbortSignal.timeout(75000),
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

function EvidenceList({ cell, busy, onAdd, onRemove }: {
  cell: ComparisonCell; busy: boolean; onAdd: () => void; onRemove: (id: string) => void;
}) {
  return <>
    <span className={`${styles.badge} ${styles[STATUS_BADGE[cell.status]]}`}>{STATUS[cell.status]}</span>
    <p className={styles.findingExplanation}>{cell.explanation}</p>
    {cell.evidence.length > 0 && <ul className={styles.evidenceList}>
      {cell.evidence.map((evidence) => {
        const isLive = evidence.id.startsWith("live:");
        return <li className={styles.evidenceItem} key={evidence.id}>
          <div className={styles.evidenceKind}>{isLive ? "Live web research" : SOURCE[evidence.source_type]}</div>
          <small className={styles.evidenceMeta}>{evidence.source_label} · {evidence.observed_on ? dateLabel(evidence.observed_on) : "No verification date"}</small>
          <p className={styles.evidenceSummary}>{evidence.summary}</p>
          {!evidence.is_demo && <p className={styles.evidenceOutcome}>{evidence.commute_minutes != null ? "Journey assessment" : "Your assessment"}: {OUTCOME[evidence.outcome]}</p>}
          {evidence.commute_minutes != null && <p className={styles.evidenceOutcome}>{evidence.commute_minutes} minutes recorded</p>}
          {evidence.source_url && <div className={styles.evidenceLinkRow}>
            <a href={evidence.source_url} target="_blank" rel="noopener noreferrer">Open source ↗</a>
            {isLive && <span className={styles.sourceToVerify}>— to verify</span>}
          </div>}
          {!evidence.is_demo && !isLive && <button type="button" className={`${styles.textBtn} ${styles.danger}`} disabled={busy} onClick={() => onRemove(evidence.id)}>Remove this note</button>}
        </li>;
      })}
    </ul>}
    <button type="button" className={styles.textBtn} disabled={busy} onClick={onAdd}>+ Record what you learned</button>
  </>;
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
  return <section className={`${styles.step} ${styles.notePanel}`} id="record-information" aria-labelledby="note-title">
    <div className={styles.noteHeading}>
      <div>
        <p className={styles.noteEyebrow}>{schoolName} · {label}</p>
        <h2 id="note-title" tabIndex={-1} ref={headingRef}>Record what you learned</h2>
      </div>
      <button type="button" className={styles.secondaryBtn} onClick={onCancel} disabled={busy}>Cancel</button>
    </div>
    {requirement.details && <p className={styles.inlineNotice}>Your requirement: {requirement.details}</p>}
    <p className={styles.stepHead} style={{ margin: "0 0 16px", fontSize: 13.5, color: "var(--ink-soft)" }}>This information is recorded by you and is not independently verified. Include the circumstances that matter to your child.</p>
    <form onSubmit={submit}>
      <fieldset disabled={busy} style={{ border: 0, padding: 0, margin: 0 }}>
        <div className={`${styles.field} ${styles.fieldPair}`}>
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
        {sourceType === "parent_experience" && <p className={styles.inlineNotice}>An individual experience adds context. It does not establish that your family’s requirement is met or unmet.</p>}
        <div className={`${styles.field} ${styles.fieldPair}`}>
          <label>Source or context
            <input name="source_label" required maxLength={200} placeholder="e.g. School office, open-house conversation" />
          </label>
          <label>Source link {sourceType !== "published_information" && "(optional)"}
            <input name="source_url" type="url" pattern="https?://.*" maxLength={2000} required={sourceType === "published_information"} placeholder="https://…" />
          </label>
        </div>
        <div className={styles.field} style={{ marginBottom: 14 }}>
          <label>What did you learn?
            <textarea name="summary" required maxLength={2000} rows={3} placeholder="Record the response or observation, including any conditions or limits." />
          </label>
        </div>
        {requirement.topic === "commute" ? <>
          <div className={styles.field} style={{ marginBottom: 8 }}>
            <label>Door-to-door travel time in minutes (optional)
              <input name="commute_minutes" type="number" min={1} max={300} step={1} placeholder="e.g. 18" />
            </label>
          </div>
          <input name="outcome" type="hidden" value="unclear" />
          <p className={styles.stepHead} style={{ fontSize: 13, margin: "0 0 16px" }}>Compared with your {requirement.max_minutes}-minute limit. Without a recorded time, the journey remains unconfirmed.</p>
        </> : <div className={styles.field} style={{ marginBottom: 16 }}>
          <label>How does this relate to your requirement?
            <select name="outcome" required defaultValue="unclear">
              <option value="unclear">It is still unclear</option>
              <option value="supports">It supports this requirement</option>
              <option value="does_not_support">It shows this requirement is not met</option>
            </select>
          </label>
        </div>}
        <button className={styles.primaryBtn} type="submit" disabled={busy}>{busy ? "Updating comparison…" : "Save note & update comparison"}</button>
      </fieldset>
    </form>
  </section>;
}

export default function HomePage() {
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null);
  const [catalogueError, setCatalogueError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [schoolNames, setSchoolNames] = useState<[string, string]>(["", ""]);
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
  const formRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);
    let disposed = false;
    setCatalogueError(null);
    async function load() {
      try {
        const response = await fetch("/api/schools", { cache: "no-store", signal: controller.signal });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error ?? "We couldn’t load the requirement list.");
        if (!disposed) setCatalogue(data);
      } catch (err) {
        if (!disposed) setCatalogueError(err instanceof Error && err.name !== "AbortError" ? err.message : "Loading the requirements took too long. Please try again.");
      } finally { clearTimeout(timeout); }
    }
    void load();
    return () => { disposed = true; clearTimeout(timeout); controller.abort(); };
  }, [retry]);

  useEffect(() => {
    if (!editing && comparison && !noteTarget) resultHeading.current?.focus();
  }, [editing, comparison, noteTarget]);

  function setImportance(topic: Topic, importance: Importance) {
    setRequirements((current) => {
      const existing = current.find((r) => r.topic === topic);
      if (importance === "not_needed") return existing ? current.filter((r) => r.topic !== topic) : current;
      if (existing) return existing.priority === importance ? current : current.map((r) => r.topic === topic ? { ...r, priority: importance } : r);
      return [...current, { id: crypto.randomUUID(), topic, priority: importance, details: "", max_minutes: topic === "commute" ? 20 : null }];
    });
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
    const names = schoolNames.map((name) => name.trim()) as [string, string];
    const ids = names.map((name, index) => schoolIdFor(name, index)) as [string, string];
    if (busy || names[0].toLowerCase() === names[1].toLowerCase() || !requirements.length) return;
    setBusy(true); setError(null);
    const request: ComparisonRequest = {
      school_ids: ids, school_names: names, context: context.trim(), requirements,
      observations: (activeRequest?.observations ?? []).filter((note) => ids.includes(note.school_id) && requirements.some((r) => r.id === note.requirement_id)),
    };
    try {
      const result = await getComparison(request);
      setComparison(result); setActiveRequest(request); setEditing(false); setChanges(null); setNoteTarget(null);
    } catch (err) { setError(err instanceof Error ? err.message : "We couldn’t compare these schools."); }
    finally { setBusy(false); }
  }
  function beginEdit() {
    if (!activeRequest) return;
    const names = activeRequest.school_names ?? activeRequest.school_ids;
    setSchoolNames(names as [string, string]); setContext(activeRequest.context); setRequirements(activeRequest.requirements);
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
  const proposedSchoolIds = schoolNames.map((name, index) => schoolIdFor(name, index)) as [string, string];
  const excludedNotes = (activeRequest?.observations ?? []).filter((note) => !proposedSchoolIds.includes(note.school_id) || !requirements.some((r) => r.id === note.requirement_id)).length;
  const duplicateSchoolNames = schoolNames[0].trim() !== "" && schoolNames[0].trim().toLowerCase() === schoolNames[1].trim().toLowerCase();
  const canSubmit = !busy && requirements.length > 0 && schoolNames[0].trim() !== "" && schoolNames[1].trim() !== "" && !duplicateSchoolNames;
  const missedMustHaves = comparison?.rows.filter((row) => row.requirement.priority === "must_have" && row.cells.some((cell) => cell.status === "not_met")) ?? [];

  return <div className={`${styles.page} ${fraunces.variable} ${editing ? styles.pageWithBar : ""}`}>
    <header className={styles.header}>
      <a href="/" className={styles.brand}>School-Fit Copilot</a>
      <nav className={styles.nav} aria-label="Main navigation">
        <a href="/" aria-current="page" className={`${styles.navLink} ${styles.navLinkActive}`}>Compare</a>
        <a href="/discover" className={styles.navLink}>Discovery demo</a>
      </nav>
    </header>

    <main className={styles.main}>
      {editing && <section className={styles.hero}>
        <h1>Two schools. Your family’s priorities.</h1>
        <p>Compare what matters, see what needs checking, and keep track of what you learn.</p>
      </section>}

      <details className={styles.notice}>
        <summary>Live research workspace — how this works, in one line</summary>
        <p>Enter real Singapore primary-school names. The comparison searches public web sources through OpenRouter and shows source leads for you to verify with each school. Do not include identifying child details; your context is sent to OpenRouter for this request and is not stored by this app. No admission odds are predicted.</p>
      </details>

      {!catalogue && <div className={styles.emptyState} role="status">
        {catalogueError ? <><p>{catalogueError}</p><button className={styles.secondaryBtn} onClick={() => setRetry((n) => n + 1)}>Retry loading requirements</button></> : "Loading requirements…"}
      </div>}

      {catalogue && editing && <form ref={formRef} onSubmit={submitComparison}>
        <fieldset disabled={busy} style={{ border: 0, padding: 0, margin: 0 }}>
          <section className={styles.step} aria-labelledby="schools-title">
            <div className={styles.stepHead}>
              <span className={styles.stepNum} aria-hidden="true">1</span>
              <div><h2 id="schools-title">Name two schools to compare</h2><p>Use the schools you are seriously considering. First check that both are realistic registration options.</p></div>
            </div>
            <div className={styles.schoolGrid}>
              {([0, 1] as const).map((index) => <div className={styles.field} key={index}>
                <label htmlFor={`school-${index}`}>School {index === 0 ? "A" : "B"}</label>
                <input id={`school-${index}`} required maxLength={120} value={schoolNames[index]} onChange={(e) => setSchoolNames((current) => index === 0 ? [e.target.value, current[1]] : [current[0], e.target.value])} placeholder={index === 0 ? "e.g. Tao Nan School" : "e.g. Nanyang Primary School"} />
              </div>)}
            </div>
            {duplicateSchoolNames && <p className={styles.errorText} role="alert" style={{ marginTop: 12 }}>Enter two different schools.</p>}
            <div className={`${styles.field} ${styles.concernField}`}>
              <label htmlFor="family-context">What is keeping you undecided? <span style={{ fontWeight: 400, color: "var(--ink-soft)" }}>(optional)</span></label>
              <textarea id="family-context" value={context} maxLength={3000} onChange={(e) => setContext(e.target.value)} placeholder="e.g. Our child gets overwhelmed by noise, and we need care after school. We’re unsure how either school handles this." rows={3} />
              <p className={styles.stepHead} style={{ margin: "8px 0 0", fontSize: 13 }}>Use the priorities below to turn your concern into specific requirements. Your notes stay in this page session.</p>
            </div>
          </section>

          <section className={styles.step} aria-labelledby="priorities-title">
            <div className={styles.stepHead}>
              <span className={styles.stepNum} aria-hidden="true">2</span>
              <div><h2 id="priorities-title">Decide what matters to your family</h2><p>Choose Preference or Must-have for each priority. Preferences cannot offset an unmet must-have.</p></div>
            </div>
            <div className={styles.priorityGrid}>
              {catalogue.topics.map((topic) => {
                const requirement = requirements.find((r) => r.topic === topic.id);
                const importance: Importance = requirement?.priority ?? "not_needed";
                return <div key={topic.id} className={`${styles.priorityCard} ${requirement ? styles.priorityCardActive : ""}`}>
                  <p className={styles.priorityTitle}>{topic.label}</p>
                  <p className={styles.priorityDesc}>{topic.description}</p>
                  <div className={styles.segment} role="group" aria-label={`Importance for ${topic.label}`}>
                    <button type="button" className={styles.segmentBtn} aria-pressed={importance === "not_needed"} onClick={() => setImportance(topic.id, "not_needed")}>Not needed</button>
                    <button type="button" className={`${styles.segmentBtn} ${importance === "preference" ? styles.segmentBtnActivePref : ""}`} aria-pressed={importance === "preference"} onClick={() => setImportance(topic.id, "preference")}>Preference</button>
                    <button type="button" className={`${styles.segmentBtn} ${importance === "must_have" ? styles.segmentBtnActiveMust : ""}`} aria-pressed={importance === "must_have"} onClick={() => setImportance(topic.id, "must_have")}>Must-have</button>
                  </div>
                  {requirement && <div className={styles.priorityDetail}>
                    {topic.id === "commute" && <label>Maximum door-to-door journey (minutes)
                      <input type="number" required min={1} max={180} step={1} value={requirement.max_minutes ?? ""} onChange={(e) => editRequirement(requirement.id, { max_minutes: e.target.value ? Number(e.target.value) : null })} />
                    </label>}
                    <label style={{ marginTop: 8 }}>What would meet this need? {topic.id !== "custom" && <span style={{ fontWeight: 400 }}>(optional)</span>}
                      <textarea rows={2} maxLength={500} required={topic.id === "custom"} value={requirement.details} onChange={(e) => editRequirement(requirement.id, { details: e.target.value })} placeholder={NOTE_PLACEHOLDER[topic.id] ?? "Describe the arrangement that would work for your child."} />
                    </label>
                  </div>}
                </div>;
              })}
            </div>
          </section>
          {error && <p className={styles.errorText} role="alert">{error}</p>}
          {excludedNotes > 0 && <p className={styles.inlineNotice}>{excludedNotes} note(s) belong to a removed school or changed requirement and will be excluded when you update. Cancel to keep the current comparison.</p>}
        </fieldset>
      </form>}
    </main>

    {catalogue && editing && <div className={styles.actionBar}>
      <span className={styles.actionSummary}>
        <strong>{requirements.length}</strong> {requirements.length === 1 ? "priority" : "priorities"} selected
        {(!schoolNames[0].trim() || !schoolNames[1].trim()) && " · name both schools to continue"}
      </span>
      <div className={styles.actionBarButtons}>
        {comparison && <button type="button" className={styles.secondaryBtn} disabled={busy} onClick={() => { setEditing(false); setError(null); }}>Cancel edits</button>}
        <button type="button" className={styles.primaryBtn} disabled={!canSubmit} onClick={() => formRef.current?.requestSubmit()}>
          {busy ? "Researching…" : comparison ? "Update schools & priorities" : "Research these schools"}
        </button>
      </div>
    </div>}

    {!editing && comparison && <main className={styles.main}>
      <div className={styles.workspaceHeading}>
        <h1 tabIndex={-1} ref={resultHeading}>Your comparison</h1>
        <button type="button" className={styles.secondaryBtn} disabled={busy || noteTarget !== null} onClick={beginEdit}>Edit schools & priorities</button>
      </div>
      {comparison.context && <div className={styles.contextBlock}><p className={styles.contextLabel}>Your deciding concern</p><p>{comparison.context}</p></div>}
      {changes !== null && <div className={styles.changesBanner} role="status">
        <strong>Comparison updated</strong>
        {changes.length ? <ul>{changes.map((change) => <li key={change}>{change}</li>)}</ul> : <p style={{ margin: "6px 0 0" }}>Your evidence changed. The requirement statuses remain the same.</p>}
      </div>}

      <div className={styles.assessmentGrid}>
        {comparison.assessments.map((assessment, index) => <article className={`${styles.assessmentCard} ${assessment.state === "unmet_requirement" ? styles.assessmentUnmet : assessment.state === "requirements_supported" ? styles.assessmentSupported : ""}`} style={{ animationDelay: `${index * 70}ms` }} key={assessment.school_id}>
          <p className={styles.assessmentEyebrow}>School {index === 0 ? "A" : "B"} · live research</p>
          <h3>{comparison.schools.find((s) => s.school_id === assessment.school_id)?.school_name}</h3>
          <span className={`${styles.badge} ${styles[ASSESSMENT_BADGE[assessment.state]]}`}>{ASSESSMENT[assessment.state]}</span>
          <p className={styles.assessmentSummary}>{assessment.summary}</p>
        </article>)}
      </div>

      {missedMustHaves.length > 0 && <div className={styles.mustHaveAlert}>
        <strong>Worth checking directly with the school</strong>
        Preferences cannot offset an unmet must-have. Confirm these before ruling either school in or out:
        <ul>{missedMustHaves.map((row) => <li key={row.requirement.id}>{row.label} — not met for {row.cells.filter((c) => c.status === "not_met").map((c) => comparison.schools.find((s) => s.school_id === c.school_id)?.school_name).join(" and ")}</li>)}</ul>
      </div>}

      {error && <p className={styles.errorText} role="alert">{error}</p>}
      {noteTarget && targetRow && targetSchool && <ObservationForm
        key={`${noteTarget.schoolId}:${noteTarget.requirementId}`}
        schoolName={targetSchool.school_name} requirement={targetRow.requirement} label={targetRow.label} busy={busy}
        onCancel={() => { setNoteTarget(null); setError(null); }}
        onSave={async (value) => { await updateNotes([...(activeRequest?.observations ?? []), { ...value, id: crypto.randomUUID(), school_id: noteTarget.schoolId, requirement_id: noteTarget.requirementId }]); }}
      />}

      <h2 className={styles.srOnly}>What the evidence tells you</h2>
      {comparison.rows.map((row, index) => <div className={styles.topicResult} style={{ animationDelay: `${140 + index * 70}ms` }} key={row.requirement.id}>
        <div className={styles.topicResultHead}>
          <p className={styles.topicResultTitle}>{row.label}</p>
          <p className={styles.topicResultMeta}>
            {row.requirement.priority === "must_have" ? "Must-have" : "Preference"}
            {row.requirement.topic === "commute" && ` · up to ${row.requirement.max_minutes} minutes door-to-door`}
            {row.requirement.details && ` · ${row.requirement.details}`}
          </p>
        </div>
        <div className={styles.findingGrid}>
          {row.cells.map((cell) => <div className={styles.findingCol} key={cell.school_id}>
            <p className={styles.findingSchoolName}>{comparison.schools.find((s) => s.school_id === cell.school_id)?.school_name}</p>
            <EvidenceList cell={cell} busy={busy || noteTarget !== null}
              onAdd={() => addNote(cell.school_id, row.requirement.id)}
              onRemove={(id) => { void updateNotes((activeRequest?.observations ?? []).filter((note) => note.id !== id)); }} />
          </div>)}
        </div>
      </div>)}

      <section className={styles.step} aria-labelledby="questions-title">
        <div className={styles.stepHead}><span className={styles.stepNum} aria-hidden="true">3</span><div><h2 id="questions-title">What to check next</h2><p>Start with your must-haves. Record the answers to update this comparison.</p></div></div>
        {comparison.questions.length === 0 ? <p>There are no unresolved requirements in your recorded information. Revisit the comparison if arrangements change.</p> : <ol className={styles.questionsList}>
          {comparison.questions.map((question) => <li className={styles.questionItem} key={question.id}>
            <div><span className={styles.questionLabel}>{comparison.schools.find((s) => s.school_id === question.school_id)?.school_name} · {question.priority === "must_have" ? "Must-have" : "Preference"}</span><p className={styles.questionText}>{question.question}</p><p className={styles.questionReason}>{question.reason}</p></div>
            <button type="button" className={styles.secondaryBtn} disabled={busy || noteTarget !== null} onClick={() => addNote(question.school_id, question.requirement_id)}>Record an answer</button>
          </li>)}
        </ol>}
      </section>
      <p className={styles.sessionNote}>{activeRequest?.observations.length ?? 0} notes in this session. Refreshing or leaving this page clears your comparison. The comparison checks your recorded requirements; it does not predict admission or your child’s future experience.</p>
    </main>}
  </div>;
}
