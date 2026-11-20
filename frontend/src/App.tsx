import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Activity, AlertTriangle, ArrowUpRight, Bot, BriefcaseBusiness, Building2, ChartNoAxesCombined, ChevronRight, CircleHelp, CreditCard, FileText, LayoutDashboard, LockKeyhole, LogOut, Package, Settings2, ShieldCheck, Users } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
type ApiStatus = "checking" | "online" | "offline";
type BusinessProfile = { name: string; industry: string; country: string; profile_image_data_url?: string | null; registration_number?: string | null; website?: string | null; contact_email?: string | null; phone?: string | null; address_line?: string | null; city?: string | null; province?: string | null; postal_code?: string | null; description?: string | null; directory_listed?: boolean; public_email?: boolean; public_phone?: boolean; public_website?: boolean; public_location?: boolean };
type PublicBusiness = { id: string; name: string; industry: string; country: string; profile_image_data_url?: string | null; website?: string | null; contact_email?: string | null; phone?: string | null; city?: string | null; province?: string | null; description?: string | null };
type NetworkInvitation = { id: string; host_business_id: string; host_business_name: string; invited_business_id: string; invited_business_name: string; invitation_message?: string | null; status: string; expires_at: string; created_at: string };
type NetworkConversation = { id: string; host_business_id: string; host_business_name: string; invited_business_id: string; invited_business_name: string; status: string; created_at: string; deal_room_id?: string | null; deal_room_status?: string | null };
type NetworkMessage = { id: string; sender_business_id: string; sender_business_name: string; sender_user_name: string; body: string; created_at: string };
type DealRoom = { id: string; conversation_id: string; status: string; created_at: string; updated_at: string };
type Quotation = { id: string; deal_room_id: string; issuer_business_id: string; issuer_business_name: string; reference: string; title: string; currency: string; line_items: {description:string;quantity:string;unit_price:string;tax_rate:string;line_subtotal:string;line_tax:string;line_total:string}[]; subtotal: string; tax_total: string; total: string; notes?: string | null; valid_until?: string | null; status: string; response_note?: string | null; created_at: string };
type QuoteLineDraft = { description: string; quantity: string; unit_price: string; tax_rate: string };
type DealFile = { id: string; deal_room_id: string; uploader_business_id: string; uploader_business_name: string; original_filename: string; content_type: string; size_bytes: number; status: string; created_at: string };
type AuthData = { access_token: string; user: { id: string; email: string; full_name: string }; business: BusinessProfile & { id: string } };
const STORAGE_KEY = "businessbrain.session";
const modules = [
  { icon: ChartNoAxesCombined, title: "Financial Intelligence", detail: "Understand your business finances", tag: "Available" },
  { icon: FileText, title: "Invoices & Quotes", detail: "Create and manage business documents", tag: "Planned" },
  { icon: Users, title: "Customers & CRM", detail: "Build stronger customer relationships", tag: "Planned" },
  { icon: Package, title: "Suppliers & Purchasing", detail: "Manage suppliers, purchase orders and goods received", tag: "Available" },
  { icon: BriefcaseBusiness, title: "People & Recruitment", detail: "Manage your team and hiring pipeline", tag: "Planned" },
  { icon: Bot, title: "AI Business Manager", detail: "Ask questions grounded in your records", tag: "Planned" },
];

function readSession(): AuthData | null {
  try {
    const value = sessionStorage.getItem(STORAGE_KEY);
    return value ? JSON.parse(value) as AuthData : null;
  } catch { return null; }
}


type PublicJob = { id: string; title: string; department?: string | null; location?: string | null; employment_type: string; description: string; requirements?: string | null; created_at: string; business_name: string; business_industry: string; business_country: string };

function PublicCareers() {
  const [jobs, setJobs] = useState<PublicJob[]>([]);
  const [query, setQuery] = useState("");
  const [selectedJob, setSelectedJob] = useState<PublicJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [form, setForm] = useState({applicant_name:"",email:"",phone:"",location:"",experience:"",resume_url:"",cover_letter:"",consent_to_share:false,website:""});

  async function loadJobs(search = "") {
    setLoading(true); setError("");
    try {
      const params = new URLSearchParams();
      if (search.trim()) params.set("q", search.trim());
      const response = await fetch(API_BASE + "/recruitment/public/jobs?" + params.toString());
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Unable to load vacancies.");
      setJobs(data as PublicJob[]);
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to load vacancies."); }
    finally { setLoading(false); }
  }
  useEffect(() => { void loadJobs(); }, []);

  async function submitApplication(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedJob) return;
    setSubmitting(true); setMessage(""); setError("");
    try {
      const response = await fetch(API_BASE + "/recruitment/public/jobs/" + selectedJob.id + "/applications", {
        method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(form)
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Your application could not be submitted.");
      setMessage(data.message || "Your application has been submitted.");
      setForm({applicant_name:"",email:"",phone:"",location:"",experience:"",resume_url:"",cover_letter:"",consent_to_share:false,website:""});
      setSelectedJob(null);
    } catch (err) { setError(err instanceof Error ? err.message : "Your application could not be submitted."); }
    finally { setSubmitting(false); }
  }

  return <div className="careers-page">
    <header className="careers-top"><a className="brand" href="/"><div className="brand-mark"><Activity size={22}/></div><span>VEXION</span></a><a className="careers-signin" href="/">Business sign in <ArrowUpRight size={15}/></a></header>
    <main className="careers-main">
      <section className="careers-hero"><div className="eyebrow">BUSINESSBRAIN CAREERS</div><h1>Find your next<br/><span>opportunity.</span></h1><p>Explore roles published by businesses on VEXION. Apply directly without creating a company account.</p><div className="careers-count">{jobs.length} {jobs.length === 1 ? "opportunity" : "opportunities"} currently listed</div></section>
      {message && <div className="careers-alert success" role="status">{message}</div>}
      <form className="careers-search" onSubmit={event=>{event.preventDefault();void loadJobs(query);}}><input aria-label="Search vacancies" value={query} onChange={event=>setQuery(event.target.value)} placeholder="Search job title, company, department or location"/><button className="auth-submit" type="submit">Search roles <ArrowUpRight size={16}/></button></form>
      {error && <div className="careers-alert" role="alert">{error}</div>}
      {loading ? <p className="careers-empty">Loading published opportunities…</p> : jobs.length === 0 ? <p className="careers-empty">No published vacancies found. Check back soon.</p> : <div className="careers-grid">{jobs.map(job=><article className="careers-job" key={job.id}><div className="careers-job-top"><span className="careers-job-type">{job.employment_type.replaceAll("_"," ")}</span><span className="careers-job-country">{job.business_country}</span></div><h2>{job.title}</h2><strong>{job.business_name}</strong><p className="careers-job-meta">{[job.department,job.location].filter(Boolean).join(" · ") || job.business_industry}</p><p className="careers-job-description">{job.description}</p>{job.requirements && <details><summary>View requirements</summary><p>{job.requirements}</p></details>}<button className="careers-apply" type="button" onClick={()=>{setSelectedJob(job);setMessage("");setError("");window.scrollTo({top:0,behavior:"smooth"});}}>Apply for this role <ArrowUpRight size={15}/></button></article>)}</div>}
      {selectedJob && <section className="careers-application" id="apply"><div className="careers-application-head"><div><div className="eyebrow">CANDIDATE APPLICATION</div><h2>{selectedJob.title}</h2><p>{selectedJob.business_name} · {selectedJob.location || selectedJob.business_country}</p></div><button className="network-close" type="button" onClick={()=>setSelectedJob(null)}>Close</button></div>
        <form className="careers-form" onSubmit={submitApplication}>
          <label>Full name<input required minLength={2} maxLength={160} autoComplete="name" value={form.applicant_name} onChange={e=>setForm({...form,applicant_name:e.target.value})}/></label>
          <label>Email address<input required type="email" maxLength={320} autoComplete="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></label>
          <label>Phone number (optional)<input type="tel" maxLength={40} value={form.phone} onChange={e=>setForm({...form,phone:e.target.value})}/></label>
          <label>Current location<input maxLength={180} value={form.location} onChange={e=>setForm({...form,location:e.target.value})} placeholder="City, province"/></label>
          <label>Experience<input maxLength={80} value={form.experience} onChange={e=>setForm({...form,experience:e.target.value})} placeholder="e.g. 2 years, graduate, entry-level"/></label>
          <label>CV link (optional)<input type="url" maxLength={500} value={form.resume_url} onChange={e=>setForm({...form,resume_url:e.target.value})} placeholder="https://…"/></label>
          <label className="careers-wide">Cover letter / introduction<textarea rows={5} maxLength={5000} value={form.cover_letter} onChange={e=>setForm({...form,cover_letter:e.target.value})} placeholder="Tell the hiring team why you are interested in this role."/></label>
          <label className="careers-honeypot" aria-hidden="true">Leave this field empty<input tabIndex={-1} autoComplete="off" value={form.website} onChange={e=>setForm({...form,website:e.target.value})}/></label>
          <label className="careers-consent careers-wide"><input required type="checkbox" checked={form.consent_to_share} onChange={e=>setForm({...form,consent_to_share:e.target.checked})}/> I consent to VEXION sharing the information in this application with the business advertising this vacancy for recruitment purposes.</label>
          {error && <div className="careers-alert careers-wide" role="alert">{error}</div>}
          <button className="auth-submit careers-wide" type="submit" disabled={submitting || !form.consent_to_share}>{submitting ? "Submitting application…" : "Submit application"} <ArrowUpRight size={16}/></button>
          <p className="careers-privacy careers-wide">Only the hiring business can view your application inside its private recruitment workspace. Do not include sensitive personal information that is not relevant to this role.</p>
        </form>
      </section>}
    </main>
    <footer className="careers-footer">VEXION © 2026 · Connecting people with opportunity.</footer>
  </div>;
}


type FinanceRecord = { id: string; kind: "income" | "expense"; category: string; description: string; amount: string; currency: string; status: "paid" | "unpaid"; occurred_on: string; reference?: string | null; notes?: string | null; payee_name?: string | null; due_on?: string | null; paid_on?: string | null; payment_method?: string | null; tax_amount?: string | null };
type FinanceSummary = { year: number; currency: string; income_total: string; manual_income_total: string; pos_sales_total: string; pos_refunds_total: string; pos_net_income_total: string; pos_transaction_count: number; expense_total: string; net_total: string; outstanding_income: string; unpaid_expenses: string; transaction_count: number; months: {month:number;income:string;expenses:string}[] };

type SalesForecastData = {
  status:"ready"|"insufficient_history";
  currency:string;
  observed_days:number;
  transaction_count:number;
  historical_totals:{sales:string;refunds:string;net_sales:string};
  history:{date:string;sales:string;refunds:string;net_sales:string;transaction_count:number}[];
  forecast:{date:string;weekday:string;observed_weekday_samples:number;projected_sales:string;projected_refunds:string;projected_net_sales:string}[];
  projected_7_day_net_sales:string|null;
  readiness:{minimum_observed_days:number;minimum_samples_per_weekday:number;ready:boolean;message:string};
  limitations:string[];
};

function FinanceWorkspace({ session }: { session: AuthData }) {
  const today = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0,10);
  const [records, setRecords] = useState<FinanceRecord[]>([]);
  const [summary, setSummary] = useState<FinanceSummary | null>(null);
  const [kindFilter, setKindFilter] = useState("all");
  const [year, setYear] = useState(new Date().getFullYear());
  const [kind, setKind] = useState<"income"|"expense">("income");
  const [category, setCategory] = useState("Sales");
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [status, setStatus] = useState<"paid"|"unpaid">("paid");
  const [occurredOn, setOccurredOn] = useState(today);
  const [reference, setReference] = useState("");
  const [notes, setNotes] = useState("");
  const [payeeName, setPayeeName] = useState("");
  const [dueOn, setDueOn] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("");
  const [taxAmount, setTaxAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [reports, setReports] = useState<{pnl:any;cash:any;vat:any}|null>(null);
  const [intelligence, setIntelligence] = useState<SalesForecastData|null>(null);
  const [bankFile, setBankFile] = useState<File|null>(null);
  const [bankAccount, setBankAccount] = useState("Main business account");
  const [bankRows, setBankRows] = useState<any[]>([]);
  const [bankBusy, setBankBusy] = useState(false);
  const [bankSuggestions, setBankSuggestions] = useState<Record<string, any[]>>({});
  const [bankSuggestionBusy, setBankSuggestionBusy] = useState<string | null>(null);
  const [bankBatchCandidates, setBankBatchCandidates] = useState<Record<string, any[]>>({});
  const [bankBatchSelections, setBankBatchSelections] = useState<Record<string, string[]>>({});
  const [bankBatchBusy, setBankBatchBusy] = useState<string | null>(null);
  async function request(path: string, method = "GET", body?: unknown) {
    const response = await fetch(API_BASE + path, { method, headers: { Authorization: "Bearer " + session.access_token, ...(body ? {"Content-Type":"application/json"} : {}) }, ...(body ? { body: JSON.stringify(body) } : {}) });
    if (response.status === 204) return null;
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Finance request failed.");
    return data;
  }
  async function loadBankRows() {
    try {
      const rows = await request("/bank-reconciliation/transactions?reconciliation_status=unmatched&limit=100");
      setBankRows(rows as any[]);
    } catch { setBankRows([]); }
  }
  async function importBankStatement() {
    if (!bankFile || bankAccount.trim().length < 2) return;
    setBankBusy(true); setError(""); setMessage("");
    try {
      const response = await fetch(API_BASE + "/bank-reconciliation/imports?filename=" + encodeURIComponent(bankFile.name) + "&account_label=" + encodeURIComponent(bankAccount.trim()), {
        method: "POST",
        headers: { Authorization: "Bearer " + session.access_token, "Content-Type": "text/csv" },
        body: await bankFile.text(),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Bank statement could not be imported.");
      setMessage("Statement imported: " + data.imported + " new rows, " + data.duplicates_skipped + " duplicates skipped.");
      setBankFile(null);
      const input = document.getElementById("vexion-bank-csv") as HTMLInputElement | null;
      if (input) input.value = "";
      await loadBankRows();
    } catch (err) { setError(err instanceof Error ? err.message : "Bank statement import failed."); }
    finally { setBankBusy(false); }
  }
  async function createFinanceFromBankRow(row: any) {
    const kind = Number(row.amount) > 0 ? "income" : "expense";
    const category = window.prompt("Choose a category for this " + kind + " entry:", kind === "income" ? "Other income" : "Operating expense");
    if (!category || !category.trim()) return;
    const description = window.prompt("Confirm the finance record description:", row.description);
    if (!description || !description.trim()) return;
    if (!window.confirm("Create a paid " + kind + " record for " + money(Math.abs(Number(row.amount))) + " using the exact bank-statement amount and date? This will update financial reports.")) return;
    setBankBusy(true); setError(""); setMessage("");
    try {
      const result = await request("/bank-reconciliation/transactions/" + row.id + "/create-finance-record", "POST", {kind, category:category.trim(), description:description.trim()});
      setMessage("Paid " + kind + " record created and linked. " + result.finance_record.amount + " " + result.finance_record.currency + " recorded.");
      setBankSuggestions(current => {const next={...current};delete next[row.id];return next;});
      await loadBankRows();
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not create finance record from bank row."); }
    finally { setBankBusy(false); }
  }
  async function reviewBankRow(row: any) {
    const note = window.prompt("Explain what you independently verified. This records a reviewer note only; it does not link an accounting source record.");
    if (!note || note.trim().length < 3) return;
    try {
      await request("/bank-reconciliation/transactions/" + row.id + "/review", "POST", { status: "matched", note: note.trim() });
      setMessage("Bank transaction review saved.");
      await loadBankRows();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save bank review."); }
  }
  async function findBankMatches(row: any) {
    setBankSuggestionBusy(row.id); setError("");
    try {
      const data = await request("/bank-reconciliation/transactions/" + row.id + "/suggestions");
      setBankSuggestions(current => ({...current, [row.id]: data.candidates || []}));
      if (!data.candidates?.length) setMessage("No exact amount/date candidates found. This bank row remains unmatched.");
    } catch (err) { setError(err instanceof Error ? err.message : "Could not find possible matches."); }
    finally { setBankSuggestionBusy(null); }
  }
  async function confirmBankMatch(row: any, candidate: any) {
    if (!window.confirm("Confirm this exact candidate link? Check the source record first. This does not independently prove bank settlement.")) return;
    setBankSuggestionBusy(row.id); setError(""); setMessage("");
    try {
      await request("/bank-reconciliation/transactions/" + row.id + "/match", "POST", {source_type:candidate.source_type,source_id:candidate.source_id});
      setMessage("Reviewer-confirmed source link saved.");
      setBankSuggestions(current => {const next={...current};delete next[row.id];return next;});
      await loadBankRows();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not confirm this match."); }
    finally { setBankSuggestionBusy(null); }
  }
  async function loadBatchCandidates(row: any) {
    setBankBatchBusy(row.id); setError("");
    try {
      const data = await request("/bank-reconciliation/transactions/" + row.id + "/batch-candidates");
      setBankBatchCandidates(current => ({...current, [row.id]: data.candidates || []}));
      setBankBatchSelections(current => ({...current, [row.id]: []}));
      if (!data.candidates?.length) setMessage("No eligible unlinked card POS transactions were found in the date window.");
    } catch (err) { setError(err instanceof Error ? err.message : "Could not load settlement batch candidates."); }
    finally { setBankBatchBusy(null); }
  }
  function toggleBatchCandidate(rowId: string, sourceId: string) {
    setBankBatchSelections(current => {
      const selected = current[rowId] || [];
      return {...current, [rowId]: selected.includes(sourceId) ? selected.filter(id => id !== sourceId) : [...selected, sourceId]};
    });
  }
  async function confirmBatchMatch(row: any) {
    const sourceIds = bankBatchSelections[row.id] || [];
    const candidates = bankBatchCandidates[row.id] || [];
    const total = candidates.filter(item => sourceIds.includes(item.source_id)).reduce((sum, item) => sum + Number(item.signed_amount), 0);
    if (sourceIds.length < 2 || Math.abs(total - Number(row.amount)) > 0.001) { setError("Select at least two POS transactions whose signed total exactly equals the bank amount."); return; }
    if (!window.confirm("Confirm " + sourceIds.length + " card POS transactions totalling " + total.toFixed(2) + "? This does not prove processor settlement or account for fees.")) return;
    setBankBatchBusy(row.id); setError(""); setMessage("");
    try {
      await request("/bank-reconciliation/transactions/" + row.id + "/batch-match", "POST", {source_ids: sourceIds});
      setMessage("Exact-total POS settlement batch linked and recorded.");
      setBankBatchCandidates(current => {const next={...current};delete next[row.id];return next;});
      setBankBatchSelections(current => {const next={...current};delete next[row.id];return next;});
      await loadBankRows();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not confirm settlement batch."); }
    finally { setBankBatchBusy(null); }
  }
  async function loadFinance() {
    setLoading(true); setError("");
    try {
      const [rows, totals, pnl, cash, vat, bi] = await Promise.all([request("/finance/transactions?year=" + year + (kindFilter === "all" ? "" : "&kind=" + kindFilter)), request("/finance/summary?year=" + year), request("/financial-reports/profit-loss?year=" + year), request("/financial-reports/cash-flow?year=" + year), request("/financial-reports/vat?year=" + year), request("/business-intelligence/sales-forecast")]);
      setRecords(rows as FinanceRecord[]); setSummary(totals as FinanceSummary); setReports({pnl, cash, vat}); setIntelligence(bi as SalesForecastData); void loadBankRows();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not load financial records."); }
    finally { setLoading(false); }
  }
  useEffect(() => { void loadFinance(); }, [session.access_token, year, kindFilter]);
  async function addRecord(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setMessage(""); setError("");
    try {
      await request("/finance/transactions", "POST", {kind,category,description,amount,status,occurred_on:occurredOn,reference:reference||null,notes:notes||null,payee_name:kind==="expense"?(payeeName||null):null,due_on:kind==="expense"?(dueOn||null):null,payment_method:kind==="expense"?(paymentMethod||null):null,tax_amount:kind==="expense"&&taxAmount?taxAmount:null});
      setDescription(""); setAmount(""); setReference(""); setNotes(""); setPayeeName(""); setDueOn(""); setPaymentMethod(""); setTaxAmount(""); setMessage("Financial record saved."); await loadFinance();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save this record."); }
    finally { setBusy(false); }
  }
  async function markExpensePaid(record: FinanceRecord) {
    setError(""); setMessage("");
    try { await request("/finance/transactions/" + record.id, "PATCH", {status:"paid",paid_on:today}); setMessage("Expense marked as paid."); await loadFinance(); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not update this expense."); }
  }
  async function deleteRecord(record: FinanceRecord) {
    if (!window.confirm("Delete this financial record? This cannot be undone.")) return;
    setError(""); setMessage("");
    try { await request("/finance/transactions/" + record.id, "DELETE"); setMessage("Record deleted."); await loadFinance(); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not delete this record."); }
  }
  const money = (value: string | number) => "R " + Number(value).toLocaleString("en-ZA", {minimumFractionDigits:2,maximumFractionDigits:2});
  const maxMonth = Math.max(1, ...(summary?.months ?? []).flatMap(item => [Number(item.income), Number(item.expenses)]));
  const posDataAvailable = (summary?.pos_transaction_count ?? 0) > 0;
  const displayedMoney = (value: string | number | undefined) => summary ? money(value ?? 0) : "—";
  return <section className="finance-centre" id="finance">
    <div className="profile-centre-heading"><div><div className="eyebrow">FINANCIAL INTELLIGENCE</div><h2>Know where your business stands.</h2><p>POS sales and refunds flow into your financial picture automatically. Record operating expenses and other non-POS income here.</p></div><span className="profile-status">Private financial workspace</span></div>
    <div className="finance-toolbar"><label>Reporting year<select value={year} onChange={e=>setYear(Number(e.target.value))}>{Array.from({length: Math.max(0, new Date().getFullYear() + 5 - 2000 + 1)}, (_, index) => new Date().getFullYear() + 5 - index).map(value=><option key={value} value={value}>{value}</option>)}</select></label><button type="button" className="network-secondary-button" onClick={()=>{void loadFinance();void loadBankRows();}}>Refresh records</button></div>
    <section className="finance-report" style={{marginBottom:24}}>
      <div className="recruitment-card-heading"><div><span className="eyebrow">BANK RECONCILIATION</span><h3>Import a bank statement</h3></div><span className="profile-status">CSV · manual review</span></div>
      <p>Upload a CSV exported from your bank. Required columns: <strong>date, description, amount</strong>. Optional: reference, transaction_id, balance, currency. Positive amounts are deposits; negative amounts are withdrawals. Imports are stored separately. A reviewer may explicitly create a paid income or expense record from an unmatched ZAR bank row; POS sales are never created or changed.</p>
      <div className="finance-toolbar"><label>Bank account label<input value={bankAccount} maxLength={120} onChange={e=>setBankAccount(e.target.value)} placeholder="e.g. Main business account"/></label><label>CSV statement<input id="vexion-bank-csv" type="file" accept=".csv,text/csv" onChange={e=>setBankFile(e.target.files?.[0]??null)}/></label><button type="button" className="network-primary-button" disabled={!bankFile||bankBusy} onClick={()=>void importBankStatement()}>{bankBusy?"Importing…":"Import statement"}</button></div>
      <div className="recruitment-card-heading" style={{marginTop:18}}><div><span className="eyebrow">NEEDS REVIEW</span><h3>Unmatched bank transactions</h3></div><span className="module-count">{bankRows.length} ROWS</span></div>
      {bankRows.length===0?<p className="network-empty">No unmatched bank statement transactions are currently recorded.</p>:<div className="finance-record-list">{bankRows.map(row=><article className="finance-record" key={row.id}><div className="finance-record-icon income">↔</div><div className="finance-record-info"><strong>{row.transaction_date} · {row.description}</strong><span>{row.reference||"No reference"} · Imported bank evidence · not yet reconciled</span>{bankSuggestions[row.id] && <div className="finance-record-list" style={{marginTop:10}}>{bankSuggestions[row.id].length===0?<small>No exact amount/date candidates found. Keep this row unmatched until verified.</small>:bankSuggestions[row.id].map((candidate:any)=><div key={candidate.source_type+candidate.source_id} className="finance-record" style={{padding:"10px 0"}}><div className="finance-record-info"><strong>{candidate.label}</strong><span>{candidate.source_type.toUpperCase()} · {candidate.source_date} · {money(candidate.amount)} · {candidate.match_basis}</span></div><button type="button" className="network-secondary-button" disabled={bankSuggestionBusy===row.id} onClick={()=>void confirmBankMatch(row,candidate)}>Confirm link</button></div>)}</div>}{bankBatchCandidates[row.id] && <div className="finance-record-list" style={{marginTop:12}}><strong>Card POS settlement candidates</strong><small>Select at least two transactions. Sales add; refunds subtract. Bank amount: {money(row.amount)}.</small>{bankBatchCandidates[row.id].length===0?<small>No eligible unlinked card transactions found.</small>:bankBatchCandidates[row.id].map((item:any)=><label key={item.source_id} className="finance-record" style={{padding:"8px 0",display:"flex",gap:10,alignItems:"center"}}><input type="checkbox" checked={(bankBatchSelections[row.id]||[]).includes(item.source_id)} onChange={()=>toggleBatchCandidate(row.id,item.source_id)}/><span className="finance-record-info"><strong>{item.transaction_type.toUpperCase()} · {item.source_date} · {item.branch||"Branch not supplied"} / {item.till||"Till not supplied"}</strong><small>{item.payment_method} · {item.external_reference||"No POS reference"} · signed {money(item.signed_amount)}</small></span></label>)}<div className="finance-toolbar"><strong>Selected total: {money((bankBatchCandidates[row.id]||[]).filter((item:any)=>(bankBatchSelections[row.id]||[]).includes(item.source_id)).reduce((sum:number,item:any)=>sum+Number(item.signed_amount),0))}</strong><button type="button" className="network-primary-button" disabled={bankBatchBusy===row.id||(bankBatchSelections[row.id]||[]).length<2} onClick={()=>void confirmBatchMatch(row)}>{bankBatchBusy===row.id?"Linking…":"Confirm exact-total batch"}</button></div></div>}</div><div className="finance-record-value"><strong>{money(row.amount)}</strong><button type="button" className="network-secondary-button" disabled={bankSuggestionBusy===row.id} onClick={()=>void findBankMatches(row)}>{bankSuggestionBusy===row.id?"Checking…":"Find matches"}</button><button type="button" className="network-secondary-button" disabled={bankBatchBusy===row.id} onClick={()=>void loadBatchCandidates(row)}>{bankBatchBusy===row.id?"Loading…":"Build POS settlement batch"}</button><button type="button" className="network-secondary-button" disabled={bankBusy||bankSuggestionBusy===row.id} onClick={()=>void createFinanceFromBankRow(row)}>Create paid {Number(row.amount)>0?"income":"expense"}</button><button type="button" className="network-secondary-button" onClick={()=>void reviewBankRow(row)}>Manual review</button></div></article>)}</div>}
      <p className="finance-disclaimer">VEXION does not connect directly to your bank in this release. Exact one-to-one suggestions and reviewer-confirmed card POS batches are available. Batch totals must equal the bank amount exactly; fees and settlement timing are not inferred. A reviewer can create a paid finance entry from an unmatched ZAR row using the exact imported amount and date. This changes the finance ledger and reports only after confirmation; POS records are never changed. Links do not independently prove bank settlement.</p>
    </section>
    {error && <p className="finance-alert" role="alert">{error}</p>}{message && <p className="finance-success" role="status">{message}</p>}
    <div className="finance-stats"><article><span>Total income</span><strong>{displayedMoney(summary?.income_total)}</strong><small>POS net sales + other paid income</small></article><article><span>POS sales</span><strong>{posDataAvailable ? money(summary?.pos_sales_total ?? 0) : "—"}</strong><small>{posDataAvailable ? `${summary?.pos_transaction_count ?? 0} POS sales/refunds · before refunds` : "No POS sales/refunds received for this year"}</small></article><article><span>POS refunds</span><strong>{posDataAvailable ? money(summary?.pos_refunds_total ?? 0) : "—"}</strong><small>{posDataAvailable ? "Deducted from POS income" : "No POS refund data received for this year"}</small></article><article><span>Expenses paid</span><strong>{displayedMoney(summary?.expense_total)}</strong><small>Paid expenses recorded</small></article><article><span>Net recorded result</span><strong className={Number(summary?.net_total ?? 0)>=0?"finance-positive":"finance-negative"}>{displayedMoney(summary?.net_total)}</strong><small>Income less paid expenses</small></article><article><span>Outstanding income</span><strong>{displayedMoney(summary?.outstanding_income)}</strong><small>Income marked unpaid</small></article></div>
    {reports && <div className="finance-stats">
      <article><span>Profit &amp; loss</span><strong>{money(reports.pnl.net_result)}</strong><small>Recorded revenue less paid manual expenses</small></article>
      <article><span>Recorded operating cash flow</span><strong>{money(reports.cash.recorded_operating_flows.net_recorded_flow)}</strong><small>POS takings/refunds and paid manual records; not bank-settled cash</small></article>
      <article><span>Output VAT on issued invoices</span><strong>{money(reports.vat.output_vat_on_issued_invoices)}</strong><small>{reports.vat.issued_invoice_count} issued invoices · input VAT not yet tracked</small></article>
    </div>}
    {reports && <div className="finance-report" style={{marginBottom:24}}>
      <div className="recruitment-card-heading"><div><span className="eyebrow">REPORTING TRANSPARENCY</span><h3>What these figures include</h3></div></div>
      <p>Profit &amp; loss uses POS sales and refunds plus paid manual income and expenses. Unpaid records are excluded. Purchase orders are not treated as expenses or cost of goods sold.</p>
      <p>Cash flow is a record-based operating movement, not a bank reconciliation. Bank data is not connected.</p>
      <p>VAT currently reports output VAT on issued VEXION invoices only. Input VAT and a VAT payable estimate are withheld until supplier tax invoices and verified purchase VAT are recorded.</p>
    </div>}
    {intelligence && <section className="finance-report" style={{marginBottom:24}} aria-label="Business intelligence and sales forecast">
      <div className="recruitment-card-heading"><div><span className="eyebrow">BUSINESS INTELLIGENCE</span><h3>POS sales trends &amp; 7-day outlook</h3></div><span className="profile-status">{intelligence.status==="ready"?"Indicative forecast":"History building"}</span></div>
      <div className="finance-stats">
        <article><span>Observed POS days</span><strong>{intelligence.observed_days}</strong><small>From {intelligence.transaction_count} received sales/refund transactions</small></article>
        <article><span>Historical net sales</span><strong>{money(intelligence.historical_totals.net_sales)}</strong><small>Recorded ZAR sales less refunds in the lookback window</small></article>
        <article><span>7-day projected net sales</span><strong>{intelligence.projected_7_day_net_sales===null?"Not available":money(intelligence.projected_7_day_net_sales)}</strong><small>{intelligence.status==="ready"?"Weekday-average projection":"No forecast generated"}</small></article>
      </div>
      {intelligence.status!=="ready" && <p className="finance-alert">{intelligence.readiness.message}</p>}
      <p className="finance-disclaimer">Forecasts use only observed POS sales/refunds from the previous 56 complete South African business days. Missing transaction days are not treated as zero. VEXION cannot yet verify feed completeness or store opening hours, so projections are indicative—not guaranteed—and are not profit, expenses, cash balances or bank settlements.</p>
      {intelligence.status==="ready" && <div className="finance-record-list">{intelligence.forecast.map(day=><article className="finance-record" key={day.date}><div className="finance-record-icon income">↗</div><div className="finance-record-info"><strong>{day.weekday} · {new Date(day.date+"T12:00:00").toLocaleDateString("en-ZA")}</strong><span>Based on {day.observed_weekday_samples} observed same-weekday samples · sales {money(day.projected_sales)} · refunds {money(day.projected_refunds)}</span></div><div className="finance-record-value"><strong>{money(day.projected_net_sales)}</strong><small>Projected net sales</small></div></article>)}</div>}
      <div className="recruitment-card-heading" style={{marginTop:20}}><div><span className="eyebrow">RECORDED HISTORY</span><h3>Recent observed POS days</h3></div><span className="module-count">{intelligence.history.length} DAYS</span></div>
      {intelligence.history.length===0?<p className="network-empty">No POS sales or refunds have been received for the selected history window. No historical trend or forecast is available.</p>:<div className="finance-record-list">{intelligence.history.slice(-14).reverse().map(day=><article className="finance-record" key={day.date}><div className="finance-record-icon income">•</div><div className="finance-record-info"><strong>{new Date(day.date+"T12:00:00").toLocaleDateString("en-ZA")}</strong><span>{day.transaction_count} received sales/refunds · sales {money(day.sales)} · refunds {money(day.refunds)}</span></div><div className="finance-record-value"><strong>{money(day.net_sales)}</strong><small>Recorded net sales</small></div></article>)}</div>}
      <ul>{intelligence.limitations.map(item=><li key={item}>{item}</li>)}</ul>
    </section>}
    <div className="finance-layout">
      <form className="finance-form" onSubmit={addRecord}><div className="recruitment-card-heading"><div><span className="eyebrow">NEW FINANCIAL RECORD</span><h3>Record other income or expense</h3></div></div>
        <div className="finance-kind-toggle"><button type="button" className={kind==="income"?"selected":""} onClick={()=>setKind("income")}>Income</button><button type="button" className={kind==="expense"?"selected":""} onClick={()=>setKind("expense")}>Expense</button></div>
        <label>Category<input required minLength={2} maxLength={80} value={category} onChange={e=>setCategory(e.target.value)} placeholder={kind==="income"?"Other income only — not POS sales":"Rent, stock, utilities…"}/></label>
        <label>Description<input required minLength={2} maxLength={240} value={description} onChange={e=>setDescription(e.target.value)} placeholder="What was this payment for?"/></label>
        {kind==="expense" && <label>Payee / supplier (optional)<input maxLength={180} value={payeeName} onChange={e=>setPayeeName(e.target.value)} placeholder="Who must be paid or was paid?"/></label>}
        <div className="finance-form-row"><label>Amount<input required type="number" inputMode="decimal" min="0.01" step="0.01" value={amount} onChange={e=>setAmount(e.target.value)} placeholder="Enter amount"/><small className="finance-input-hint">Enter the number in South African rand (R).</small></label><label>Date<input required type="date" value={occurredOn} onChange={e=>setOccurredOn(e.target.value)}/></label></div>
        <div className="finance-form-row"><label>Payment status<select value={status} onChange={e=>setStatus(e.target.value as "paid"|"unpaid")}><option value="paid">Paid</option><option value="unpaid">Unpaid / outstanding</option></select></label><label>Reference (optional)<input maxLength={100} value={reference} onChange={e=>setReference(e.target.value)} placeholder="Receipt / invoice no."/></label></div>
        {kind==="expense" && <><div className="finance-form-row"><label>Due date (optional)<input type="date" value={dueOn} onChange={e=>setDueOn(e.target.value)}/></label><label>Payment method (optional)<select value={paymentMethod} onChange={e=>setPaymentMethod(e.target.value)}><option value="">Not recorded</option><option value="cash">Cash</option><option value="card">Card</option><option value="eft">EFT / bank transfer</option><option value="debit_order">Debit order</option><option value="other">Other</option></select></label></div><label>VAT amount shown on supplier document (optional)<input type="number" min="0" step="0.01" value={taxAmount} onChange={e=>setTaxAmount(e.target.value)} placeholder="Enter only if shown on the document"/></label></>}
        <label>Notes (optional)<textarea rows={3} maxLength={2000} value={notes} onChange={e=>setNotes(e.target.value)} placeholder="Additional details…"/></label>
        <button className="auth-submit" type="submit" disabled={busy}>{busy?"Saving record…":"Save financial record"} <ArrowUpRight size={16}/></button>
        <p className="finance-disclaimer">POS sales and refunds are imported automatically from received POS transactions. Use manual income only for income outside POS sales, to avoid double-counting. Expense payees, due dates and payment details are manually recorded; supplier VAT is captured for reference only and is not included in VAT reports. Only owners and administrators can add or update records.</p>
      </form>
      <div className="finance-report"><div className="recruitment-card-heading"><div><span className="eyebrow">MONTHLY CASH MOVEMENT</span><h3>{year} overview</h3></div><span className="module-count">{summary?.transaction_count ?? 0} RECORDS</span></div>
        <div className="finance-chart">{(summary?.months ?? []).map(item=><div className="finance-month" key={item.month}><div className="finance-bars"><span title={"Income "+money(item.income)} style={{height:Math.max(2,Number(item.income)/maxMonth*100)+"%"}}/><span title={"Expenses "+money(item.expenses)} style={{height:Math.max(2,Number(item.expenses)/maxMonth*100)+"%"}}/></div><small>{new Date(year,item.month-1,1).toLocaleString("en-ZA",{month:"short"})}</small></div>)}</div>
        <div className="finance-legend"><span><i className="income-dot"/>Income</span><span><i className="expense-dot"/>Expenses</span></div><div className="finance-outstanding"><span>Unpaid expenses</span><strong>{displayedMoney(summary?.unpaid_expenses)}</strong></div>
      </div>
    </div>
    <div className="finance-records"><div className="recruitment-card-heading"><div><span className="eyebrow">YOUR BOOKKEEPING</span><h3>Financial records</h3></div><select aria-label="Filter financial records" value={kindFilter} onChange={e=>setKindFilter(e.target.value)}><option value="all">All records</option><option value="income">Income only</option><option value="expense">Expenses only</option></select></div>
      {loading?<p className="network-empty">Loading financial records…</p>:records.length===0?<p className="network-empty">No financial records for this year yet. Add your first income or expense above.</p>:<div className="finance-record-list">{records.map(record=>{const overdue=record.kind==="expense"&&record.status==="unpaid"&&!!record.due_on&&record.due_on<today;return <article className="finance-record" key={record.id}><div className={"finance-record-icon "+record.kind}>{record.kind==="income"?"↗":"↘"}</div><div className="finance-record-info"><strong>{record.description}</strong><span>{record.category} · {new Date(record.occurred_on+"T12:00:00").toLocaleDateString("en-ZA")} · {record.payee_name||"No payee"} · {record.reference||"No reference"}</span>{record.kind==="expense"&&<small>{record.due_on?`Due ${new Date(record.due_on+"T12:00:00").toLocaleDateString("en-ZA")}`:"No due date"}{record.payment_method?` · ${record.payment_method.replace("_"," ")}`:""}{record.tax_amount?` · VAT captured ${money(record.tax_amount)}`:""}</small>}{overdue&&<small className="finance-record-status unpaid">Overdue · requires payment review</small>}</div><div className="finance-record-value"><strong>{money(record.amount)}</strong><small className={"finance-record-status "+record.status}>{record.status}</small></div>{record.kind==="expense"&&record.status==="unpaid"&&<button type="button" className="network-secondary-button" onClick={()=>void markExpensePaid(record)}>Mark paid</button>}<button type="button" className="network-secondary-button" onClick={()=>void deleteRecord(record)}>Delete</button></article>})}</div>}
    </div>
  </section>;
}



type DailyCloseRow = {
  id:string; business_date:string; branch_name:string; currency:string; timezone_name:string; source_type:"pos"|"manual"; pos_transaction_count:number;
  expected_cash:string; expected_card:string; expected_other:string; expected_total:string|null;
  actual_cash:string; actual_card:string; actual_other:string; actual_total:string; expenses_total:string;
  variance_cash:string|null; variance_card:string|null; variance_other:string|null; variance_total:string|null;
  notes?:string|null; status:string; review_note?:string|null;
};
type ReconciliationData = {
  status:"manual_baseline"|"pos_data_missing"|"source_changed"|"reconciled";
  message:string;
  pos_transaction_count:number;
  pos_totals:{cash:string;card:string;other:string}|null;
  actual_received:{cash:string;card:string;other:string};
  variance_vs_pos:{cash:string;card:string;other:string}|null;
};
function DailyCloseWorkspace({session}:{session:AuthData}) {
  const today=new Date(Date.now()-new Date().getTimezoneOffset()*60000).toISOString().slice(0,10);
  const [businessDate,setBusinessDate]=useState(today);
  const [branch,setBranch]=useState("Main branch");
  const [expectedCash,setExpectedCash]=useState("");
  const [expectedCard,setExpectedCard]=useState("");
  const [expectedOther,setExpectedOther]=useState("0");
  const [actualCash,setActualCash]=useState("");
  const [actualCard,setActualCard]=useState("");
  const [actualOther,setActualOther]=useState("0");
  const [expenses,setExpenses]=useState("0");
  const [notes,setNotes]=useState("");
  const [rows,setRows]=useState<DailyCloseRow[]>([]);
  const [selected,setSelected]=useState<DailyCloseRow|null>(null);
  const [reconciliation,setReconciliation]=useState<ReconciliationData|null>(null);
  const [reconciliationLoading,setReconciliationLoading]=useState(false);
  const [caseBusy,setCaseBusy]=useState(false);
  const [reviewNote,setReviewNote]=useState("");
  const [busy,setBusy]=useState(false);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");
  async function request(path:string,method="GET",body?:unknown) {
    const response=await fetch(API_BASE+path,{method,headers:{Authorization:"Bearer "+session.access_token,...(body?{"Content-Type":"application/json"}:{})},...(body?{body:JSON.stringify(body)}:{})});
    const data=await response.json();
    if(!response.ok)throw new Error(data.detail||"Daily close request failed.");
    return data;
  }
  async function load() {
    setLoading(true);setError("");
    try {const data=await request("/daily-closes") as DailyCloseRow[];setRows(data);}
    catch(e){setError(e instanceof Error?e.message:"Could not load daily closes.");}
    finally{setLoading(false);}
  }
  useEffect(()=>{void load();},[session.access_token]);
  async function save(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();setBusy(true);setError("");setMessage("");
    try {
      const data=await request("/daily-closes","POST",{
        business_date:businessDate,branch_name:branch,timezone_name:Intl.DateTimeFormat().resolvedOptions().timeZone||"Africa/Johannesburg",
        expected_cash:expectedCash===""?null:expectedCash,expected_card:expectedCard===""?null:expectedCard,expected_other:expectedOther===""?null:expectedOther,
        actual_cash:actualCash,actual_card:actualCard,actual_other:actualOther,expenses_total:expenses,notes:notes||null
      }) as DailyCloseRow;
      setSelected(data);void loadReconciliation(data);setMessage(data.source_type==="pos"?"Saved. Expected totals were calculated from matching POS transactions.":"Saved as a manual close because no matching POS transactions were found.");
      await load();
    } catch(e){setError(e instanceof Error?e.message:"Could not save this close.");}
    finally{setBusy(false);}
  }
  async function loadReconciliation(row:DailyCloseRow) {
    setReconciliationLoading(true);
    setReconciliation(null);
    try {
      const result=await request("/daily-closes/"+row.id+"/reconciliation") as ReconciliationData;
      setReconciliation(result);
    } catch(e) {
      setError(e instanceof Error?e.message:"Could not refresh the POS reconciliation.");
    } finally {
      setReconciliationLoading(false);
    }
  }
  async function createCaseFromReconciliation(row:DailyCloseRow) {
    if(!reconciliation || !reconciliation.variance_vs_pos) return;
    const differences=Object.entries(reconciliation.variance_vs_pos).filter(([,value])=>Number(value)!==0);
    if(differences.length===0) return;
    setCaseBusy(true);setError("");setMessage("");
    try {
      const existing=await request("/discrepancies") as {daily_close_id:string|null;category:string;status:string}[];
      const openCase=existing.find(item=>item.daily_close_id===row.id&&item.category==="reconciliation"&&item.status!=="resolved");
      if(openCase) {
        setMessage("An active reconciliation case already exists for this daily close. Open it in Discrepancy Management to continue the investigation.");
        return;
      }
      const lines=differences.map(([bucket,value])=>bucket.toUpperCase()+": "+(Number(value)>0?"+":"")+"R "+Number(value).toLocaleString("en-ZA",{minimumFractionDigits:2,maximumFractionDigits:2}));
      const singleAmount=differences.length===1?differences[0][1]:null;
      const detail=[
        "Created from the current POS reconciliation for "+row.branch_name+" on "+row.business_date+".",
        "Current POS totals: "+Object.entries(reconciliation.pos_totals||{}).map(([key,value])=>key+" R "+Number(value).toFixed(2)).join("; ")+".",
        "Amounts counted/confirmed: "+Object.entries(reconciliation.actual_received||{}).map(([key,value])=>key+" R "+Number(value).toFixed(2)).join("; ")+".",
        "Variance (actual received minus current POS): "+lines.join("; ")+".",
        "This case records a difference for investigation. It does not change the daily close or POS transactions."
      ].join("\n");
      await request("/discrepancies","POST",{
        daily_close_id:row.id,
        title:"POS reconciliation difference — "+row.branch_name+" · "+row.business_date,
        description:detail,
        category:"reconciliation",
        priority:"normal",
        amount:singleAmount,
        currency:row.currency
      });
      setMessage("Reconciliation case created. Open Discrepancy Management to assign and investigate it.");
      window.setTimeout(()=>document.getElementById("discrepancies")?.scrollIntoView({behavior:"smooth",block:"start"}),150);
    } catch(e) {
      setError(e instanceof Error?e.message:"Could not create the reconciliation case.");
    } finally {
      setCaseBusy(false);
    }
  }
  async function submitClose(row:DailyCloseRow) {
    setBusy(true);setError("");setMessage("");
    try {const data=await request("/daily-closes/"+row.id+"/submit","POST") as DailyCloseRow;setSelected(data);setMessage("Daily close submitted for manager review.");await load();}
    catch(e){setError(e instanceof Error?e.message:"Could not submit this close.");}
    finally{setBusy(false);}
  }
  async function review(row:DailyCloseRow,decision:"approved"|"requires_attention") {
    setBusy(true);setError("");setMessage("");
    try {const data=await request("/daily-closes/"+row.id+"/review","POST",{decision,note:reviewNote||null}) as DailyCloseRow;setSelected(data);setReviewNote("");setMessage(decision==="approved"?"Daily close approved.":"Daily close returned for attention.");await load();}
    catch(e){setError(e instanceof Error?e.message:"Could not review this close.");}
    finally{setBusy(false);}
  }
  const money=(v:string|null)=>v===null?"Not available":"R "+Number(v).toLocaleString("en-ZA",{minimumFractionDigits:2,maximumFractionDigits:2});
  return <section className="finance-centre" id="daily-close">
    <div className="profile-centre-heading"><div><div className="eyebrow">VEXION BUSINESS CONTROL</div><h2>Daily business close.</h2><p>Reconcile expected receipts against counted cash, card settlements and other payments. Submit each day for review.</p></div><span className="profile-status">Audited workflow</span></div>
    <div className="finance-stats">
      <article><span>Awaiting review</span><strong>{rows.filter(row=>row.status==="submitted").length}</strong><small>Submitted daily closes</small></article>
      <article><span>Needs attention</span><strong>{rows.filter(row=>row.status==="requires_attention").length}</strong><small>Returned for correction</small></article>
      <article><span>Approved</span><strong>{rows.filter(row=>row.status==="approved").length}</strong><small>Reviewed daily closes</small></article>
      <article><span>Recorded days</span><strong>{rows.length}</strong><small>Latest 100 business days</small></article>
    </div>
    {error&&<p className="finance-alert" role="alert">{error}</p>}{message&&<p className="finance-success" role="status">{message}</p>}
    <div className="pos-layout">
      <form className="finance-form" onSubmit={save}>
        <div className="recruitment-card-heading"><div><span className="eyebrow">CLOSE A BUSINESS DAY</span><h3>Record the day's figures</h3></div></div>
        <label>Business date<input type="date" required value={businessDate} onChange={e=>setBusinessDate(e.target.value)}/></label>
        <label>Branch / store<input required maxLength={160} value={branch} onChange={e=>setBranch(e.target.value)} /></label>
        <p className="finance-disclaimer">Expected totals are taken from matching POS transactions when available. Otherwise enter the expected figures from your till/Z report. Actual figures must be counted or confirmed by staff.</p>
        <div className="profile-fields-grid">
          <label>Expected cash (R)<input type="number" min="0" step="0.01" value={expectedCash} onChange={e=>setExpectedCash(e.target.value)} placeholder="0.00"/></label>
          <label>Expected card (R)<input type="number" min="0" step="0.01" value={expectedCard} onChange={e=>setExpectedCard(e.target.value)} placeholder="0.00"/></label>
          <label>Expected other (R)<input type="number" min="0" step="0.01" value={expectedOther} onChange={e=>setExpectedOther(e.target.value)}/></label>
          <label>Cash counted (R)<input type="number" min="0" step="0.01" required value={actualCash} onChange={e=>setActualCash(e.target.value)} placeholder="0.00"/></label>
          <label>Card settled / confirmed (R)<input type="number" min="0" step="0.01" required value={actualCard} onChange={e=>setActualCard(e.target.value)} placeholder="0.00"/></label>
          <label>Other received (R)<input type="number" min="0" step="0.01" required value={actualOther} onChange={e=>setActualOther(e.target.value)}/></label>
          <label>Expenses recorded for the day (R)<input type="number" min="0" step="0.01" required value={expenses} onChange={e=>setExpenses(e.target.value)}/></label>
        </div>
        <label>Closing notes<textarea maxLength={4000} value={notes} onChange={e=>setNotes(e.target.value)} placeholder="Explain unusual items, missing slips or cash count notes."/></label>
        <button className="auth-submit" type="submit" disabled={busy}>{busy?"Saving…":"Save daily close"} <ArrowUpRight size={16}/></button>
      </form>
      <div className="finance-form">
        <div className="recruitment-card-heading"><div><span className="eyebrow">REVIEW QUEUE</span><h3>Recent daily closes</h3></div><button type="button" className="network-secondary-button" onClick={()=>void load()}>Refresh</button></div>
        {loading?<p className="network-empty">Loading daily closes…</p>:rows.length===0?<p className="network-empty">No daily closes recorded yet. Start with your first branch and business date.</p>:<div className="finance-record-list">{rows.map(row=><button type="button" key={row.id} className="finance-record-row" onClick={()=>{setSelected(row);void loadReconciliation(row);}}><span><strong>{row.branch_name}</strong><small>{row.business_date} · {row.source_type==="pos"?"POS reconciled":"Manual figures"}</small></span><span><strong>{row.status.replace("_"," ")}</strong><small>Variance: {money(row.variance_total)}</small></span></button>)}</div>}
      </div>
    </div>
    {selected&&<div className="finance-form daily-close-detail">
      <div className="recruitment-card-heading"><div><span className="eyebrow">RECONCILIATION DETAIL</span><h3>{selected.branch_name} · {selected.business_date}</h3></div><span className="profile-status">{selected.status.replace("_"," ")}</span></div>
      <div className="finance-stats">
        <article><span>Expected total</span><strong>{money(selected.expected_total)}</strong><small>{selected.source_type==="pos"?selected.pos_transaction_count+" POS transactions":"Manual till report figures"}</small></article>
        <article><span>Actual received</span><strong>{money(selected.actual_total)}</strong><small>Cash + card + other</small></article>
        <article><span>Difference</span><strong className={Number(selected.variance_total??0)===0?"finance-positive":"finance-negative"}>{money(selected.variance_total)}</strong><small>Actual less expected</small></article>
        <article><span>Expenses</span><strong>{money(selected.expenses_total)}</strong><small>Separately recorded</small></article>
      </div>
      <div className="profile-fields-grid">
        <p>Cash difference: <strong>{money(selected.variance_cash)}</strong></p><p>Card difference: <strong>{money(selected.variance_card)}</strong></p><p>Other difference: <strong>{money(selected.variance_other)}</strong></p>
      </div>
      <div className="finance-form">
        <div className="recruitment-card-heading"><div><span className="eyebrow">LIVE POS RECHECK</span><h3>Current source reconciliation</h3></div><button type="button" className="network-secondary-button" disabled={reconciliationLoading} onClick={()=>void loadReconciliation(selected)}>{reconciliationLoading?"Checking…":"Refresh POS check"}</button></div>
        {reconciliationLoading?<p className="network-empty">Checking the current POS ledger…</p>:!reconciliation?<p className="network-empty">Select refresh to check whether current POS records still match this saved close.</p>:<>
          <p className="finance-disclaimer">{reconciliation.message}</p>
          <div className="profile-fields-grid">
            <p>Reconciliation status: <strong>{reconciliation.status.replaceAll("_"," ")}</strong></p>
            <p>Current POS transactions: <strong>{reconciliation.pos_transaction_count}</strong></p>
            {reconciliation.pos_totals&&Object.entries(reconciliation.pos_totals).map(([key,value])=><p key={key}>POS {key}: <strong>{money(value)}</strong></p>)}
            {reconciliation.variance_vs_pos&&Object.entries(reconciliation.variance_vs_pos).map(([key,value])=><p key={key}>{key} variance: <strong>{money(value)}</strong></p>)}
          </div>
          {reconciliation.variance_vs_pos&&Object.values(reconciliation.variance_vs_pos).some(value=>Number(value)!==0)&&<button type="button" className="auth-submit" disabled={caseBusy} onClick={()=>void createCaseFromReconciliation(selected)}>{caseBusy?"Creating case…":"Create investigation case from this difference"} <ArrowUpRight size={16}/></button>}
          {(reconciliation.status==="manual_baseline"||reconciliation.status==="pos_data_missing")&&<p className="finance-disclaimer">A case cannot be generated from a POS comparison because there is no verifiable POS baseline available for this close.</p>}
        </>}
      </div>
      {selected.notes&&<p>{selected.notes}</p>}{selected.review_note&&<p className="finance-alert">Review note: {selected.review_note}</p>}
      {selected.status==="draft"&&<button type="button" className="auth-submit" disabled={busy} onClick={()=>void submitClose(selected)}>Submit for manager review</button>}
      {selected.status==="submitted"&&<><label>Review note<textarea value={reviewNote} onChange={e=>setReviewNote(e.target.value)} placeholder="Optional note for the staff member."/></label><div className="pos-actions"><button type="button" className="auth-submit" disabled={busy} onClick={()=>void review(selected,"approved")}>Approve close</button><button type="button" className="network-secondary-button" disabled={busy} onClick={()=>void review(selected,"requires_attention")}>Return for attention</button></div></>}
    </div>}
    <p className="finance-disclaimer">A variance is a discrepancy requiring review, not proof of wrongdoing. VEXION only calculates against records supplied or connected to the business. The review history is retained for audit purposes.</p>
  </section>;
}

type POSConnectionData = { id:string; provider_name:string; display_name:string; integration_method:"api"|"webhook"|"local_agent"; status:string; created_at:string; last_received_at?:string|null; webhook_secret?:string };
type POSSalesData = { days:number; transaction_count:number; sales_total:string; refunds_total:string; net_sales:string; void_count:number };
function POSConnectionsWorkspace({session}:{session:AuthData}) {
  const [connections,setConnections] = useState<POSConnectionData[]>([]);
  const [summary,setSummary] = useState<POSSalesData|null>(null);
  const [provider,setProvider] = useState("");
  const [displayName,setDisplayName] = useState("Main till");
  const [method,setMethod] = useState<"api"|"webhook"|"local_agent">("webhook");
  const [secret,setSecret] = useState("");
  const [loading,setLoading] = useState(true);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState("");
  const [message,setMessage] = useState("");
  async function request(path:string,methodName="GET",body?:unknown) {
    const response=await fetch(API_BASE+path,{method:methodName,headers:{Authorization:"Bearer "+session.access_token,...(body?{"Content-Type":"application/json"}:{})},...(body?{body:JSON.stringify(body)}:{})});
    const data=await response.json();
    if(!response.ok) throw new Error(data.detail||"VEXION POS request failed.");
    return data;
  }
  async function load() {
    setLoading(true);setError("");
    try { const [items,totals]=await Promise.all([request("/pos/connections"),request("/pos/summary?days=7")]);setConnections(items as POSConnectionData[]);setSummary(totals as POSSalesData); }
    catch(e){setError(e instanceof Error?e.message:"Could not load POS connections.");}
    finally{setLoading(false);}
  }
  useEffect(()=>{void load();},[session.access_token]);
  async function create(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();setBusy(true);setError("");setMessage("");setSecret("");
    try {const result=await request("/pos/connections","POST",{provider_name:provider,display_name:displayName,integration_method:method}) as POSConnectionData;setSecret(result.webhook_secret||"");setMessage("Connection created. Copy the secret now; it will not be shown again.");setProvider("");await load();}
    catch(e){setError(e instanceof Error?e.message:"Could not create POS connection.");}
    finally{setBusy(false);}
  }
  async function rotate(id:string) {
    setError("");setMessage("");setSecret("");
    try {const result=await request("/pos/connections/"+id+"/rotate-secret","POST");setSecret(result.webhook_secret);setMessage("A new secret was created. Update your connector; the previous secret is no longer valid.");}
    catch(e){setError(e instanceof Error?e.message:"Could not rotate connection secret.");}
  }
  async function disable(id:string) {
    if(!window.confirm("Disable this POS connection? New transactions will no longer be accepted."))return;
    try {await request("/pos/connections/"+id+"/disable","POST");setMessage("POS connection disabled.");await load();}
    catch(e){setError(e instanceof Error?e.message:"Could not disable connection.");}
  }
  const money=(v:string)=>"R "+Number(v).toLocaleString("en-ZA",{minimumFractionDigits:2,maximumFractionDigits:2});
  return <section className="pos-workspace" id="pos-connections">
    <div className="profile-centre-heading"><div><div className="eyebrow">VEXION CONNECT</div><h2>Connect your existing POS system.</h2><p>Bring sales from your current tills into one secure business intelligence workspace. No till replacement is required.</p></div><span className="profile-status">POS-agnostic foundation</span></div>
    <div className="pos-stats">
      <article><span>Sales received · 7 days</span><strong>{money(summary?.sales_total??"0")}</strong></article>
      <article><span>Refunds · 7 days</span><strong>{money(summary?.refunds_total??"0")}</strong></article>
      <article><span>Net sales · 7 days</span><strong>{money(summary?.net_sales??"0")}</strong></article>
      <article><span>Transactions received</span><strong>{summary?.transaction_count??0}</strong></article>
    </div>
    {error&&<p className="finance-alert" role="alert">{error}</p>}{message&&<p className="finance-success" role="status">{message}</p>}
    {secret&&<div className="pos-secret"><strong>One-time connector secret</strong><p>Copy this into the approved POS connector or integration service. VEXION stores only a one-way hash.</p><code>{secret}</code><button type="button" className="network-secondary-button" onClick={()=>void navigator.clipboard.writeText(secret)}>Copy secret</button></div>}
    <div className="pos-layout">
      <form className="finance-form" onSubmit={create}><div className="recruitment-card-heading"><div><span className="eyebrow">NEW CONNECTION</span><h3>Register a POS system</h3></div></div>
        <label>POS provider / brand<input required minLength={2} maxLength={120} value={provider} onChange={e=>setProvider(e.target.value)} placeholder="e.g. POS provider name"/></label>
        <label>Connection name<input required minLength={2} maxLength={160} value={displayName} onChange={e=>setDisplayName(e.target.value)} placeholder="e.g. Durban store · Till 1"/></label>
        <label>Connection method<select value={method} onChange={e=>setMethod(e.target.value as typeof method)}><option value="webhook">Webhook</option><option value="api">Direct API / integration service</option><option value="local_agent">Local connector agent</option></select></label>
        <button className="auth-submit" type="submit" disabled={busy}>{busy?"Creating connection…":"Create POS connection"} <ArrowUpRight size={16}/></button>
        <p className="finance-disclaimer">Creating a connection does not automatically connect a POS vendor. Each provider still needs a tested API, webhook or authorised local connector.</p>
      </form>
      <div className="pos-connection-list"><div className="recruitment-card-heading"><div><span className="eyebrow">YOUR INTEGRATIONS</span><h3>POS connections</h3></div><button type="button" className="network-secondary-button" onClick={()=>void load()}>Refresh</button></div>
        {loading?<p className="network-empty">Loading connections…</p>:connections.length===0?<p className="network-empty">No POS systems connected yet. Register your first till to begin setup.</p>:connections.map(item=><article className="pos-connection" key={item.id}><div><strong>{item.display_name}</strong><span>{item.provider_name} · {item.integration_method.replace("_"," ")}</span><small>Last data: {item.last_received_at?new Date(item.last_received_at).toLocaleString("en-ZA"):"No transactions received yet"}</small></div><span className={"pos-status "+item.status}>{item.status}</span><div className="pos-actions"><button type="button" className="network-secondary-button" onClick={()=>void rotate(item.id)} disabled={item.status==="disabled"}>Rotate secret</button><button type="button" className="network-secondary-button" onClick={()=>void disable(item.id)} disabled={item.status==="disabled"}>Disable</button></div></article>)}
      </div>
    </div>
    <POSCsvImport session={session} connections={connections} onImported={()=>void load()} />
  </section>;
}



function POSCsvImport({session,connections,onImported}:{session:AuthData;connections:POSConnectionData[];onImported:()=>void}) {
  const [file,setFile]=useState<File|null>(null); const [connectionId,setConnectionId]=useState(""); const [headers,setHeaders]=useState<string[]>([]); const [mapping,setMapping]=useState<Record<string,string>>({}); const [busy,setBusy]=useState(false); const [error,setError]=useState(""); const [result,setResult]=useState<{imported:number;duplicates:number;rejected:{row:number;reason:string}[]}|null>(null);
  async function chooseFile(next:File|null){setFile(next);setHeaders([]);setMapping({});setResult(null);setError("");if(!next)return;if(!next.name.toLowerCase().endsWith(".csv")){setError("Please choose a .csv file.");return;}if(next.size>5*1024*1024){setError("CSV files must be 5 MB or smaller.");return;}try{const first=(await next.text()).replace(/^\\uFEFF/,"").split(/\r?\n/,1)[0];const parsed=first.split(",").map(value=>value.trim().replace(/^"|"$/g,""));if(!parsed.length||!parsed[0])throw new Error("The CSV needs a header row.");setHeaders(parsed);const suggestions:Record<string,string>={};const aliases:Record<string,string[]>={external_transaction_id:["id","transaction id","receipt","receipt no","receipt number","transaction"],occurred_at:["date","datetime","date time","timestamp","transaction date"],gross_amount:["gross","gross amount","total","amount"],net_amount:["net","net amount","total","amount"],discount_amount:["discount","discount amount"],tax_amount:["tax","vat","tax amount"],branch_name:["branch","store","store name"],till_name:["till","terminal","register"],payment_method:["payment","payment method","tender"],transaction_type:["type","transaction type"],currency:["currency"]};for(const [field,names] of Object.entries(aliases)){const found=parsed.find(header=>names.includes(header.toLowerCase()));if(found)suggestions[field]=found;}setMapping(suggestions);}catch(e){setError(e instanceof Error?e.message:"Could not read this CSV file.");}}
  async function importFile(){if(!file||!connectionId)return;const required=["external_transaction_id","occurred_at","gross_amount","net_amount"];if(required.some(field=>!mapping[field])){setError("Map transaction ID, date/time, gross amount and net amount before importing.");return;}setBusy(true);setError("");setResult(null);try{const response=await fetch(API_BASE+"/pos/connections/"+connectionId+"/import-csv",{method:"POST",headers:{"Content-Type":"application/json",Authorization:"Bearer "+session.access_token},body:JSON.stringify({csv_text:await file.text(),mapping})});const data=await response.json();if(!response.ok)throw new Error(data.detail||"CSV import failed.");setResult(data);onImported();}catch(e){setError(e instanceof Error?e.message:"CSV import failed.");}finally{setBusy(false);}}
  const fields:[string,string,boolean][]=[["external_transaction_id","Transaction ID",true],["occurred_at","Date / time",true],["gross_amount","Gross amount",true],["net_amount","Net amount",true],["discount_amount","Discount",false],["tax_amount","Tax / VAT",false],["branch_name","Branch / store",false],["till_name","Till / terminal",false],["payment_method","Payment method",false],["transaction_type","Transaction type",false],["currency","Currency",false]];
  return <section className="pos-workspace"><div className="profile-centre-heading"><div><div className="eyebrow">VEXION CONNECT · FILE IMPORT</div><h2>Import sales from a POS export.</h2><p>Upload an approved CSV export from your till system. Match its columns, then bring verified transactions into Sales Intelligence.</p></div><span className="profile-status">CSV · up to 5 MB</span></div><div className="pos-create-form"><label>POS connection<select value={connectionId} onChange={e=>setConnectionId(e.target.value)} required><option value="">Choose a connection</option>{connections.filter(item=>item.status!=="disabled").map(item=><option key={item.id} value={item.id}>{item.display_name} · {item.provider_name}</option>)}</select></label><label>Choose POS CSV export<input type="file" accept=".csv,text/csv" onChange={e=>void chooseFile(e.target.files?.[0]??null)}/></label>{file&&<p className="directory-message">{file.name} · {(file.size/1024).toFixed(1)} KB · {headers.length} columns detected</p>}{headers.length>0&&<div className="profile-fields-grid">{fields.map(([field,label,required])=><label key={field}>{label}{required?" *":" optional"}<select value={mapping[field]||""} onChange={e=>setMapping(current=>({...current,[field]:e.target.value}))}><option value="">Not mapped</option>{headers.map(header=><option key={header} value={header}>{header}</option>)}</select></label>)}</div>}{error&&<p className="finance-alert" role="alert">{error}</p>}<button className="auth-submit" type="button" disabled={busy||!file||!connectionId||headers.length===0} onClick={()=>void importFile()}>{busy?"Importing transactions…":"Validate and import CSV"} <ArrowUpRight size={16}/></button>{result&&<div className="finance-success" role="status"><strong>Import completed.</strong> {result.imported} imported · {result.duplicates} duplicates skipped · {result.rejected.length} rejected.{result.rejected.length>0&&<ul>{result.rejected.slice(0,8).map(item=><li key={item.row}>Row {item.row}: {item.reason}</li>)}</ul>}</div>}<p className="finance-disclaimer">Only import sales exports you are authorised to share. VEXION does not import card numbers or customer payment credentials. CSV imports use the same duplicate checks as connected POS feeds.</p></div></section>;
}

type SalesDailyRow = {date:string;sales:string;refunds:string;net_sales:string;transaction_count:number;void_count:number};
type SalesBranchRow = {branch:string;sales:string;refunds:string;net_sales:string;transaction_count:number;void_count:number};
type SalesTillRow = {branch:string;till:string;net_sales:string;transaction_count:number};
function SalesIntelligenceWorkspace({session}:{session:AuthData}) {
  const [daily,setDaily]=useState<SalesDailyRow[]>([]);
  const [branches,setBranches]=useState<SalesBranchRow[]>([]);
  const [tills,setTills]=useState<SalesTillRow[]>([]);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");
  async function load(){
    setLoading(true);setError("");
    try{
      const headers={Authorization:"Bearer "+session.access_token};
      const [d,b,t]=await Promise.all([
        fetch(API_BASE+"/pos/analytics/daily?days=30&currency=ZAR",{headers}),
        fetch(API_BASE+"/pos/analytics/branches?days=30&currency=ZAR",{headers}),
        fetch(API_BASE+"/pos/analytics/tills?days=30&currency=ZAR",{headers})
      ]);
      const [dd,bd,td]=await Promise.all([d.json(),b.json(),t.json()]);
      if(!d.ok)throw new Error(dd.detail||"Could not load daily sales.");
      if(!b.ok)throw new Error(bd.detail||"Could not load branch sales.");
      if(!t.ok)throw new Error(td.detail||"Could not load till sales.");
      setDaily(dd.items as SalesDailyRow[]);setBranches(bd.items as SalesBranchRow[]);setTills(td.items as SalesTillRow[]);
    }catch(e){setError(e instanceof Error?e.message:"Sales analytics could not be loaded.");}
    finally{setLoading(false);}
  }
  useEffect(()=>{void load();},[session.access_token]);
  const money=(v:string)=>"R "+Number(v).toLocaleString("en-ZA",{minimumFractionDigits:2,maximumFractionDigits:2});
  const totalSales=daily.reduce((n,x)=>n+Number(x.sales),0);
  const totalRefunds=daily.reduce((n,x)=>n+Number(x.refunds),0);
  const maxDaily=Math.max(1,...daily.map(x=>Number(x.net_sales)));
  return <section className="sales-workspace" id="sales-intelligence">
    <div className="profile-centre-heading"><div><div className="eyebrow">VEXION SALES INTELLIGENCE</div><h2>Understand how your stores are performing.</h2><p>Review POS-reported sales, refunds, net sales and branch performance across the last 30 days.</p></div><button type="button" className="network-secondary-button" onClick={()=>void load()}>Refresh sales</button></div>
    <div className="pos-stats"><article><span>Gross POS sales · 30 days</span><strong>{money(totalSales.toFixed(2))}</strong></article><article><span>Refunds · 30 days</span><strong>{money(totalRefunds.toFixed(2))}</strong></article><article><span>Net sales · 30 days</span><strong>{money((totalSales-totalRefunds).toFixed(2))}</strong></article><article><span>POS transactions</span><strong>{daily.reduce((n,x)=>n+x.transaction_count,0).toLocaleString("en-ZA")}</strong></article></div>
    {error&&<p className="finance-alert" role="alert">{error}</p>}
    <div className="sales-layout">
      <div className="sales-panel"><div className="recruitment-card-heading"><div><span className="eyebrow">DAILY TREND</span><h3>Net sales by day</h3></div><span className="module-count">LAST 30 DAYS</span></div>
        {loading?<p className="network-empty">Loading sales data…</p>:daily.length===0?<p className="network-empty">No POS sales data yet. Connect a till and start receiving transactions to see performance here.</p>:<div className="sales-bars">{daily.map(item=><div className="sales-bar-column" key={item.date}><div className="sales-bar-track"><span style={{height:Math.max(3,Number(item.net_sales)/maxDaily*100)+"%"}} title={money(item.net_sales)}/></div><small>{new Date(item.date+"T12:00:00").toLocaleDateString("en-ZA",{day:"2-digit",month:"short"})}</small></div>)}</div>}
      </div>
      <div className="sales-panel"><div className="recruitment-card-heading"><div><span className="eyebrow">BRANCH PERFORMANCE</span><h3>Compare your stores</h3></div></div>
        {loading?<p className="network-empty">Loading branches…</p>:branches.length===0?<p className="network-empty">Branch comparisons will appear once POS transactions include branch names.</p>:<div className="sales-branch-list">{branches.map(item=><article key={item.branch}><div><strong>{item.branch}</strong><small>{item.transaction_count} transactions · {item.void_count} voids</small></div><b>{money(item.net_sales)}</b></article>)}</div>}
      </div>
    </div>
    <div className="sales-panel sales-tills"><div className="recruitment-card-heading"><div><span className="eyebrow">TILL PERFORMANCE</span><h3>Sales by till</h3></div></div>{loading?<p className="network-empty">Loading tills…</p>:tills.length===0?<p className="network-empty">Till comparisons will appear when POS transactions include till names.</p>:<div className="sales-branch-list">{tills.map((item,index)=><article key={item.branch+"-"+item.till+"-"+index}><div><strong>{item.branch} · {item.till}</strong><small>{item.transaction_count} transactions</small></div><b>{money(item.net_sales)}</b></article>)}</div>}</div>
  </section>;
}
type InvoiceLineDraft = {description:string;quantity:string;unit_price:string;tax_rate:string};
type InvoiceData = {id:string;invoice_number:string;customer_name:string;customer_email?:string|null;issue_date:string;due_date:string;currency:string;status:string;subtotal:string;tax_total:string;total:string;created_at:string;lines:{description:string;quantity:string;unit_price:string;tax_rate:string;line_total:string}[]};
function InvoiceWorkspace({session}:{session:AuthData}) {
  const today=new Date(Date.now()-new Date().getTimezoneOffset()*60000).toISOString().slice(0,10);
  const [invoices,setInvoices]=useState<InvoiceData[]>([]);
  const [customer,setCustomer]=useState("");
  const [email,setEmail]=useState("");
  const [phone,setPhone]=useState("");
  const [address,setAddress]=useState("");
  const [issueDate,setIssueDate]=useState(today);
  const [dueDate,setDueDate]=useState(today);
  const [currency,setCurrency]=useState("ZAR");
  const [notes,setNotes]=useState("");
  const [lines,setLines]=useState<InvoiceLineDraft[]>([{description:"",quantity:"1",unit_price:"",tax_rate:"15"}]);
  const [loading,setLoading]=useState(true);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");
  async function request(path:string,method="GET",body?:unknown){
    const response=await fetch(API_BASE+path,{method,headers:{Authorization:"Bearer "+session.access_token,...(body?{"Content-Type":"application/json"}:{})},...(body?{body:JSON.stringify(body)}:{})});
    const data=await response.json();
    if(!response.ok)throw new Error(data.detail||"Invoice request failed.");
    return data;
  }
  async function load(){setLoading(true);setError("");try{setInvoices(await request("/invoices") as InvoiceData[]);}catch(e){setError(e instanceof Error?e.message:"Invoices could not be loaded.");}finally{setLoading(false);}}
  useEffect(()=>{void load();},[session.access_token]);
  function updateLine(index:number,patch:Partial<InvoiceLineDraft>){setLines(current=>current.map((line,i)=>i===index?{...line,...patch}:line));}
  async function create(event:FormEvent<HTMLFormElement>){
    event.preventDefault();setBusy(true);setError("");setMessage("");
    try{
      const created=await request("/invoices","POST",{customer_name:customer,customer_email:email||null,customer_phone:phone||null,customer_address:address||null,issue_date:issueDate,due_date:dueDate,currency,notes:notes||null,lines}) as InvoiceData;
      setMessage("Invoice "+created.invoice_number+" created as a draft.");setCustomer("");setEmail("");setPhone("");setAddress("");setNotes("");setLines([{description:"",quantity:"1",unit_price:"",tax_rate:"15"}]);await load();
    }catch(e){setError(e instanceof Error?e.message:"Invoice could not be created.");}
    finally{setBusy(false);}
  }
  async function updateStatus(invoice:InvoiceData,status:"sent"|"paid"|"overdue"|"cancelled"){
    setError("");setMessage("");
    try{await request("/invoices/"+invoice.id+"/status","PATCH",{status});setMessage(invoice.invoice_number+" marked "+status+".");await load();}
    catch(e){setError(e instanceof Error?e.message:"Invoice status could not be updated.");}
  }
  const preview=lines.reduce((total,line)=>{const subtotal=Number(line.quantity||0)*Number(line.unit_price||0);return total+subtotal+subtotal*Number(line.tax_rate||0)/100;},0);
  return <section className="invoice-workspace" id="invoices">
    <div className="profile-centre-heading"><div><div className="eyebrow">VEXION INVOICE CENTRE</div><h2>Create and track professional invoices.</h2><p>Build itemised invoices with VAT, due dates and payment status in one place.</p></div><span className="profile-status">Invoice records</span></div>
    {error&&<p className="finance-alert" role="alert">{error}</p>}{message&&<p className="finance-success" role="status">{message}</p>}
    <div className="invoice-layout">
      <form className="finance-form" onSubmit={create}><div className="recruitment-card-heading"><div><span className="eyebrow">NEW INVOICE</span><h3>Invoice details</h3></div></div>
        <label>Customer / company<input required minLength={2} maxLength={180} value={customer} onChange={e=>setCustomer(e.target.value)} placeholder="Customer name"/></label>
        <div className="finance-form-row"><label>Customer email<input type="email" maxLength={320} value={email} onChange={e=>setEmail(e.target.value)} placeholder="accounts@customer.co.za"/></label><label>Customer phone<input type="tel" maxLength={40} value={phone} onChange={e=>setPhone(e.target.value)} placeholder="Optional"/></label></div>
        <label>Customer address<textarea rows={2} maxLength={2000} value={address} onChange={e=>setAddress(e.target.value)} placeholder="Billing address (optional)"/></label>
        <div className="finance-form-row"><label>Invoice date<input type="date" required value={issueDate} onChange={e=>setIssueDate(e.target.value)}/></label><label>Due date<input type="date" required min={issueDate} value={dueDate} onChange={e=>setDueDate(e.target.value)}/></label></div>
        <label>Currency<select value={currency} onChange={e=>setCurrency(e.target.value)}><option value="ZAR">South African rand (ZAR)</option><option value="USD">US dollar (USD)</option><option value="GBP">Pound sterling (GBP)</option><option value="EUR">Euro (EUR)</option></select></label>
        <div className="invoice-lines-heading"><strong>Invoice items</strong><button type="button" className="network-secondary-button" onClick={()=>setLines(current=>[...current,{description:"",quantity:"1",unit_price:"",tax_rate:"15"}])}>Add item</button></div>
        {lines.map((line,index)=><div className="invoice-line-editor" key={index}><label>Description<input required minLength={2} maxLength={240} value={line.description} onChange={e=>updateLine(index,{description:e.target.value})} placeholder="Product or service"/></label><div className="invoice-line-fields"><label>Qty<input required type="number" min="0.001" step="0.001" value={line.quantity} onChange={e=>updateLine(index,{quantity:e.target.value})}/></label><label>Unit price<input required type="number" min="0" step="0.01" value={line.unit_price} onChange={e=>updateLine(index,{unit_price:e.target.value})}/></label><label>VAT %<input required type="number" min="0" max="100" step="0.01" value={line.tax_rate} onChange={e=>updateLine(index,{tax_rate:e.target.value})}/></label><button type="button" className="network-secondary-button" disabled={lines.length===1} onClick={()=>setLines(current=>current.filter((_,i)=>i!==index))}>Remove</button></div></div>)}
        <label>Notes / payment terms<textarea rows={2} maxLength={3000} value={notes} onChange={e=>setNotes(e.target.value)} placeholder="Payment instructions or additional notes"/></label>
        <div className="invoice-preview-total"><span>Estimated total including VAT</span><strong>{currency} {preview.toLocaleString("en-ZA",{minimumFractionDigits:2,maximumFractionDigits:2})}</strong></div>
        <button className="auth-submit" type="submit" disabled={busy}>{busy?"Creating invoice…":"Create draft invoice"} <ArrowUpRight size={16}/></button>
        <p className="finance-disclaimer">VAT is calculated per line. Creating an invoice does not automatically record income in Expenses & Profit, preventing duplicate revenue.</p>
      </form>
      <div className="invoice-list-panel"><div className="recruitment-card-heading"><div><span className="eyebrow">INVOICE REGISTER</span><h3>Your invoices</h3></div><button type="button" className="network-secondary-button" onClick={()=>void load()}>Refresh</button></div>
        {loading?<p className="network-empty">Loading invoices…</p>:invoices.length===0?<p className="network-empty">No invoices yet. Create your first draft invoice.</p>:invoices.map(invoice=><article className="invoice-record" key={invoice.id}><div className="invoice-record-main"><div><strong>{invoice.invoice_number}</strong><span>{invoice.customer_name} · Due {new Date(invoice.due_date+"T12:00:00").toLocaleDateString("en-ZA")}</span></div><b>{invoice.currency} {Number(invoice.total).toLocaleString("en-ZA",{minimumFractionDigits:2,maximumFractionDigits:2})}</b></div><div className="invoice-record-actions"><span className={"invoice-status "+invoice.status}>{invoice.status}</span>{invoice.status==="draft"&&<button type="button" className="network-secondary-button" onClick={()=>void updateStatus(invoice,"sent")}>Mark sent</button>}{(invoice.status==="sent"||invoice.status==="overdue")&&<button type="button" className="network-secondary-button" onClick={()=>void updateStatus(invoice,"paid")}>Mark paid</button>}</div><small>{invoice.lines.length} item{invoice.lines.length===1?"":"s"} · Issued {new Date(invoice.issue_date+"T12:00:00").toLocaleDateString("en-ZA")}</small></article>)}
      </div>
    </div>
    <p className="finance-disclaimer">Email delivery and PDF download are not enabled in this release. Invoice creation, VAT calculations and status tracking are live; sending and downloadable document generation are the next invoice-centre steps.</p>
  </section>;
}



type DiscrepancyRow = {id:string;daily_close_id:string|null;title:string;description:string;category:string;priority:string;status:string;amount:string|null;currency:string;assigned_to_user_id:string|null;resolution_note:string|null;created_at:string;updated_at:string};
type DiscrepancyDetail = DiscrepancyRow & {events:{id:string;actor_user_id:string;event_type:string;details:Record<string,string>;created_at:string}[]};
type EvidenceRow = {id:string;discrepancy_id:string;original_filename:string;content_type:string;size_bytes:number;status:string;uploader_user_id:string;created_at:string;scanned_at:string|null};
function DiscrepancyWorkspace({session}:{session:AuthData}) {
  const [items,setItems]=useState<DiscrepancyRow[]>([]);
  const [staff,setStaff]=useState<{user_id:string;full_name:string;role:string}[]>([]);
  const [closes,setCloses]=useState<DailyCloseRow[]>([]);
  const [selected,setSelected]=useState<DiscrepancyDetail|null>(null);
  const [evidence,setEvidence]=useState<EvidenceRow[]>([]);
  const [evidenceFile,setEvidenceFile]=useState<File|null>(null);
  const [evidenceBusy,setEvidenceBusy]=useState(false);
  const [title,setTitle]=useState("");
  const [description,setDescription]=useState("");
  const [category,setCategory]=useState("reconciliation");
  const [priority,setPriority]=useState("normal");
  const [amount,setAmount]=useState("");
  const [closeId,setCloseId]=useState("");
  const [assignee,setAssignee]=useState("");
  const [note,setNote]=useState("");
  const [filter,setFilter]=useState("all");
  const [loading,setLoading]=useState(true);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");
  async function request(path:string,method="GET",body?:unknown) {
    const response=await fetch(API_BASE+path,{method,headers:{Authorization:"Bearer "+session.access_token,...(body?{"Content-Type":"application/json"}:{})},...(body?{body:JSON.stringify(body)}:{})});
    const data=await response.json();
    if(!response.ok)throw new Error(data.detail||"Discrepancy request failed.");
    return data;
  }
  async function load() {
    setLoading(true);setError("");
    try {
      const [rows,members,days]=await Promise.all([request("/discrepancies"+(filter==="all"?"":"?status="+filter)),request("/staff"),request("/daily-closes")]);
      setItems(rows as DiscrepancyRow[]);setStaff(members as typeof staff);setCloses(days as DailyCloseRow[]);
      if(selected){const fresh=await request("/discrepancies/"+selected.id) as DiscrepancyDetail;setSelected(fresh);}
    } catch(e){setError(e instanceof Error?e.message:"Could not load discrepancy records.");}
    finally{setLoading(false);}
  }
  useEffect(()=>{void load();},[session.access_token,filter]);
  async function create(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();setBusy(true);setError("");setMessage("");
    try {
      const item=await request("/discrepancies","POST",{title,description,category,priority,amount:amount||null,currency:"ZAR",daily_close_id:closeId||null,assigned_to_user_id:assignee||null}) as DiscrepancyRow;
      setTitle("");setDescription("");setAmount("");setCloseId("");setAssignee("");setMessage("Discrepancy case opened and added to the investigation register.");
      await load();setSelected(await request("/discrepancies/"+item.id) as DiscrepancyDetail);
    } catch(e){setError(e instanceof Error?e.message:"Could not create discrepancy.");}
    finally{setBusy(false);}
  }
  async function loadEvidence(caseId:string){const rows=await request("/discrepancies/"+caseId+"/evidence") as EvidenceRow[];setEvidence(rows);}
  async function openItem(item:DiscrepancyRow){try{setSelected(await request("/discrepancies/"+item.id) as DiscrepancyDetail);await loadEvidence(item.id);}catch(e){setError(e instanceof Error?e.message:"Could not open discrepancy.");}}
  async function uploadEvidence(event:FormEvent<HTMLFormElement>){event.preventDefault();if(!selected||!evidenceFile)return;setEvidenceBusy(true);setError("");setMessage("");try{const ticket=await request("/discrepancies/"+selected.id+"/evidence/upload-url","POST",{filename:evidenceFile.name,content_type:evidenceFile.type,size_bytes:evidenceFile.size}) as {evidence_id:string;upload_url:string;fields:Record<string,string>};const form=new FormData();Object.entries(ticket.fields).forEach(([key,value])=>form.append(key,value));form.append("file",evidenceFile);const uploaded=await fetch(ticket.upload_url,{method:"POST",body:form});if(!uploaded.ok)throw new Error("The private storage upload failed. The evidence remains unavailable.");await request("/discrepancies/evidence/"+ticket.evidence_id+"/complete","POST");setEvidenceFile(null);const picker=document.getElementById("discrepancy-evidence-picker") as HTMLInputElement|null;if(picker)picker.value="";await loadEvidence(selected.id);setSelected(await request("/discrepancies/"+selected.id) as DiscrepancyDetail);setMessage("Evidence uploaded, scanned and attached to this case.");}catch(e){setError(e instanceof Error?e.message:"Evidence upload failed.");}finally{setEvidenceBusy(false);}}
  async function downloadEvidence(item:EvidenceRow){try{const result=await request("/discrepancies/evidence/"+item.id+"/download-url","POST") as {download_url:string};window.open(result.download_url,"_blank","noopener,noreferrer");}catch(e){setError(e instanceof Error?e.message:"Could not download evidence.");}}
  async function update(item:DiscrepancyDetail,patch:Record<string,unknown>){setBusy(true);setError("");setMessage("");try{await request("/discrepancies/"+item.id,"PATCH",patch);setMessage("Discrepancy updated.");await load();setSelected(await request("/discrepancies/"+item.id) as DiscrepancyDetail);}catch(e){setError(e instanceof Error?e.message:"Could not update discrepancy.");}finally{setBusy(false);}}
  async function addNote(event:FormEvent<HTMLFormElement>){event.preventDefault();if(!selected||!note.trim())return;setBusy(true);setError("");try{await request("/discrepancies/"+selected.id+"/notes","POST",{note});setNote("");setSelected(await request("/discrepancies/"+selected.id) as DiscrepancyDetail);setMessage("Investigation note added to the audit timeline.");}catch(e){setError(e instanceof Error?e.message:"Could not add investigation note.");}finally{setBusy(false);}}
  const money=(value:string|null)=>value===null?"Amount not recorded": "R "+Number(value).toLocaleString("en-ZA",{minimumFractionDigits:2,maximumFractionDigits:2});
  return <section className="finance-centre" id="discrepancies">
    <div className="profile-centre-heading"><div><div className="eyebrow">VEXION CONTROL & RESOLUTION</div><h2>Discrepancy management.</h2><p>Turn differences into assigned, documented investigations. A discrepancy is a review item, not proof of wrongdoing.</p></div><span className="profile-status"><AlertTriangle size={14}/> Case register</span></div>
    {error&&<p className="finance-alert" role="alert">{error}</p>}{message&&<p className="finance-success" role="status">{message}</p>}
    <div className="finance-stats">
      <article><span>Open</span><strong>{items.filter(x=>x.status==="open").length}</strong><small>Awaiting investigation</small></article>
      <article><span>Investigating</span><strong>{items.filter(x=>x.status==="investigating").length}</strong><small>Assigned / in progress</small></article>
      <article><span>Resolved</span><strong>{items.filter(x=>x.status==="resolved").length}</strong><small>Resolution documented</small></article>
      <article><span>Urgent</span><strong>{items.filter(x=>x.priority==="urgent"&&x.status!=="resolved").length}</strong><small>Requires priority attention</small></article>
    </div>
    <div className="pos-layout">
      <form className="finance-form" onSubmit={create}>
        <div className="recruitment-card-heading"><div><span className="eyebrow">NEW CASE</span><h3>Record a discrepancy</h3></div></div>
        <label>Case title<input required minLength={3} maxLength={180} value={title} onChange={e=>setTitle(e.target.value)} placeholder="e.g. Cash count differs from POS"/></label>
        <label>What needs investigation?<textarea required minLength={5} maxLength={4000} rows={4} value={description} onChange={e=>setDescription(e.target.value)} placeholder="Record what was observed, where it occurred and what needs checking."/></label>
        <div className="finance-form-row"><label>Category<select value={category} onChange={e=>setCategory(e.target.value)}><option value="reconciliation">Reconciliation</option><option value="pos_data">POS data</option><option value="cash">Cash</option><option value="card">Card settlement</option><option value="expense">Expense</option><option value="other">Other</option></select></label><label>Priority<select value={priority} onChange={e=>setPriority(e.target.value)}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option><option value="urgent">Urgent</option></select></label></div>
        <div className="finance-form-row"><label>Amount (optional)<input type="number" step="0.01" value={amount} onChange={e=>setAmount(e.target.value)} placeholder="Only enter a verified amount"/></label><label>Link daily close (optional)<select value={closeId} onChange={e=>setCloseId(e.target.value)}><option value="">No linked daily close</option>{closes.map(c=><option key={c.id} value={c.id}>{c.business_date} · {c.branch_name}</option>)}</select></label></div>
        <label>Assign to team member (optional)<select value={assignee} onChange={e=>setAssignee(e.target.value)}><option value="">Unassigned</option>{staff.map(member=><option key={member.user_id} value={member.user_id}>{member.full_name} · {member.role}</option>)}</select></label>
        <button className="auth-submit" type="submit" disabled={busy}>{busy?"Opening case…":"Open discrepancy case"} <ArrowUpRight size={16}/></button>
        <p className="finance-disclaimer">Amounts are optional and must come from verified records. Linking a daily close does not change that close or create a financial adjustment.</p>
      </form>
      <div className="finance-report">
        <div className="recruitment-card-heading"><div><span className="eyebrow">INVESTIGATION QUEUE</span><h3>Discrepancy register</h3></div><select aria-label="Filter discrepancy status" value={filter} onChange={e=>setFilter(e.target.value)}><option value="all">All cases</option><option value="open">Open</option><option value="investigating">Investigating</option><option value="resolved">Resolved</option></select></div>
        {loading?<p className="network-empty">Loading discrepancy records…</p>:items.length===0?<p className="network-empty">No discrepancy cases recorded. Differences are not automatically labelled as wrongdoing; create a case when a real item needs investigation.</p>:<div className="finance-record-list">{items.map(item=><button type="button" className="finance-record-row" key={item.id} onClick={()=>void openItem(item)}><span><strong>{item.title}</strong><small>{item.category.replaceAll("_"," ")} · {item.priority} · {new Date(item.created_at).toLocaleDateString("en-ZA")}</small></span><span><strong>{item.status.replaceAll("_"," ")}</strong><small>{money(item.amount)}</small></span></button>)}</div>}
      </div>
    </div>
    {selected&&<div className="finance-form daily-close-detail">
      <div className="recruitment-card-heading"><div><span className="eyebrow">CASE FILE</span><h3>{selected.title}</h3></div><span className="profile-status">{selected.status}</span></div>
      <p>{selected.description}</p><div className="profile-fields-grid"><p>Priority: <strong>{selected.priority}</strong></p><p>Category: <strong>{selected.category.replaceAll("_"," ")}</strong></p><p>Amount: <strong>{money(selected.amount)}</strong></p><p>Linked close: <strong>{selected.daily_close_id?"Yes":"No"}</strong></p></div>
      <div className="finance-form-row"><label>Assigned team member<select value={selected.assigned_to_user_id||""} onChange={e=>void update(selected,{assigned_to_user_id:e.target.value||null})}><option value="">Unassigned</option>{staff.map(member=><option key={member.user_id} value={member.user_id}>{member.full_name}</option>)}</select></label><label>Case status<select value={selected.status} onChange={e=>{const next=e.target.value;if(next==="resolved"){const resolution=window.prompt("Enter the resolution note before closing this case:");if(resolution&&resolution.trim().length>=3)void update(selected,{status:next,resolution_note:resolution});}else void update(selected,{status:next});}}><option value="open">Open</option><option value="investigating">Investigating</option><option value="resolved">Resolved</option></select></label></div>
      {selected.resolution_note&&<p className="finance-success">Resolution: {selected.resolution_note}</p>}
      <form className="message-compose" onSubmit={addNote}><input required minLength={2} maxLength={4000} value={note} onChange={e=>setNote(e.target.value)} placeholder="Add an investigation note…"/><button type="submit" disabled={busy}>Add note</button></form>
      <section className="finance-form"><div className="recruitment-card-heading"><div><span className="eyebrow">SUPPORTING DOCUMENTATION</span><h3>Case evidence</h3></div><span className="profile-status">{evidence.length} files</span></div><p className="finance-disclaimer">Upload receipts, POS reports, settlement statements or other supporting records. Files stay private to this business and are only available after malware scanning succeeds. Maximum 25 MB per file.</p><form className="deal-file-upload" onSubmit={uploadEvidence}><label className="deal-file-picker">Choose evidence<input id="discrepancy-evidence-picker" type="file" accept=".pdf,.docx,.xlsx,.pptx,.txt,.csv,.png,.jpg,.jpeg" onChange={e=>setEvidenceFile(e.target.files?.[0]??null)}/></label><span className="deal-file-selected">{evidenceFile?evidenceFile.name+" · "+(evidenceFile.size/1024/1024).toFixed(2)+" MB":"PDF, Office documents, TXT, CSV or images"}</span><button className="network-primary-button" type="submit" disabled={!evidenceFile||evidenceBusy}>{evidenceBusy?"Uploading and scanning…":"Upload evidence"}</button></form><div className="deal-file-list">{evidence.map(file=><article className="deal-file-card" key={file.id}><div className="deal-file-icon"><FileText size={18}/></div><div className="deal-file-info"><strong>{file.original_filename}</strong><span>{(file.size_bytes/1024/1024).toFixed(2)} MB · Malware scan passed · {new Date(file.created_at).toLocaleString("en-ZA")}</span></div><button type="button" className="network-secondary-button" onClick={()=>void downloadEvidence(file)}>Secure download</button></article>)}{evidence.length===0&&<p className="network-empty">No evidence files attached to this case yet.</p>}</div></section><div className="discrepancy-timeline"><strong>Audit timeline</strong>{selected.events.map(event=><article key={event.id}><span>{event.event_type.replaceAll("_"," ")}</span><small>{new Date(event.created_at).toLocaleString("en-ZA")}</small>{event.details.note&&<p>{event.details.note}</p>}{event.details.filename&&<p>File: {event.details.filename}</p>}{event.details.to&&<p>Status: {event.details.from} → {event.details.to}</p>}</article>)}</div>
    </div>}
    <p className="finance-disclaimer">Case changes, notes and evidence actions are recorded with the acting user and timestamp. Uploaded evidence is private and must pass malware scanning before it can be downloaded.</p>
  </section>;
}

type BillingOverview = {
  currency: string;
  subscription_status: string;
  payment_status: string;
  active_pos_terminals: number;
  inactive_pos_terminals: number;
  verified_direct_referrals: number;
  referral_discount_eligible: boolean;
  unit_price_per_pos_month: string;
  estimated_monthly_total: string;
  standard_unit_price: string;
  referral_unit_price: string;
  notice: string;
  terminals: {id:string;external_terminal_id:string;display_name:string;branch_name?:string|null;connection_id?:string|null;source?:string;status:string;created_at:string}[];
};

function BillingWorkspace({session}:{session:AuthData}) {
  const [data,setData]=useState<BillingOverview|null>(null);
  const [loading,setLoading]=useState(true);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");
  const [terminalId,setTerminalId]=useState("");
  const [terminalName,setTerminalName]=useState("");
  const [branchName,setBranchName]=useState("");

  async function request(path:string,method="GET",body?:unknown) {
    const response=await fetch(API_BASE+path,{method,headers:{Authorization:"Bearer "+session.access_token,...(body?{"Content-Type":"application/json"}:{})},...(body?{body:JSON.stringify(body)}:{})});
    const result=await response.json();
    if(!response.ok) throw new Error(result.detail||"Billing request failed.");
    return result;
  }
  async function load() {
    setLoading(true);setError("");
    try {setData(await request("/billing/me") as BillingOverview);}
    catch(err) {setError(err instanceof Error?err.message:"Billing information could not be loaded.");}
    finally {setLoading(false);}
  }
  useEffect(()=>{void load();},[session.access_token]);

  async function registerTerminal(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();setBusy(true);setError("");setMessage("");
    try {
      await request("/billing/terminals","POST",{external_terminal_id:terminalId.trim(),display_name:terminalName.trim(),branch_name:branchName.trim()||null});
      setTerminalId("");setTerminalName("");setBranchName("");
      setMessage("POS terminal registered. Your estimate has been refreshed.");
      await load();
    } catch(err) {setError(err instanceof Error?err.message:"POS terminal could not be registered.");}
    finally {setBusy(false);}
  }
  async function setTerminalStatus(id:string,status:"active"|"inactive") {
    setError("");setMessage("");
    try {await request("/billing/terminals/"+id,"PATCH",{status});setMessage("POS terminal status updated.");await load();}
    catch(err) {setError(err instanceof Error?err.message:"POS terminal status could not be updated.");}
  }
  const money=(value:string)=>"R "+Number(value).toLocaleString("en-ZA",{minimumFractionDigits:2,maximumFractionDigits:2});

  return <section className="billing-workspace" id="billing">
    <div className="profile-centre-heading"><div><div className="eyebrow">VEXION SUBSCRIPTION</div><h2>POS-based pricing and subscription overview.</h2><p>Track registered tills and see the estimated monthly price for your business.</p></div><span className="profile-status">Payment setup pending</span></div>
    {error&&<p className="finance-alert" role="alert">{error}</p>}{message&&<p className="finance-success" role="status">{message}</p>}
    {loading?<p className="network-empty">Loading billing overview…</p>:data&&<>
      <div className="billing-stats">
        <article><span>Active registered POS</span><strong>{data.active_pos_terminals}</strong><small>{data.inactive_pos_terminals} inactive</small></article>
        <article><span>Price per POS / month</span><strong>{money(data.unit_price_per_pos_month)}</strong><small>{data.referral_discount_eligible?"Five direct paid referrals verified":"Standard monthly price"}</small></article>
        <article><span>Estimated monthly total</span><strong>{money(data.estimated_monthly_total)}</strong><small>Based on active registered POS</small></article>
        <article><span>Verified referrals</span><strong>{data.verified_direct_referrals} / 5</strong><small>{data.referral_discount_eligible?"Referral price unlocked":"Five paying referrals required"}</small></article>
      </div>
      <div className="billing-price-note"><strong>Pricing rules</strong><span>R499 per active POS terminal each month. After five directly referred businesses have verified paid subscriptions, your rate becomes R399 per active POS terminal each month.</span></div>
      <div className="billing-columns">
        <form className="finance-form" onSubmit={registerTerminal}>
          <div className="recruitment-card-heading"><div><span className="eyebrow">POS REGISTER</span><h3>Add a POS terminal</h3></div></div>
          <label>Terminal / till ID<input required minLength={1} maxLength={180} value={terminalId} onChange={e=>setTerminalId(e.target.value)} placeholder="e.g. TILL-01 or POS serial number"/></label>
          <label>Display name<input required minLength={2} maxLength={160} value={terminalName} onChange={e=>setTerminalName(e.target.value)} placeholder="e.g. Front counter"/></label>
          <label>Branch / location (optional)<input maxLength={160} value={branchName} onChange={e=>setBranchName(e.target.value)} placeholder="e.g. Durban branch"/></label>
          <button className="auth-submit" type="submit" disabled={busy}>{busy?"Registering…":"Register POS terminal"} <ArrowUpRight size={16}/></button>
          <p className="finance-disclaimer">Only register genuine POS terminals belonging to this business. Connected POS feeds automatically add tills here when transactions include a till name and branch. Manual registration remains available for tills that have not reported yet.</p>
        </form>
        <div className="billing-terminal-list">
          <div className="recruitment-card-heading"><div><span className="eyebrow">REGISTERED EQUIPMENT</span><h3>Your POS terminals</h3></div><button type="button" className="network-secondary-button" onClick={()=>void load()}>Refresh</button></div>
          {data.terminals.length===0?<p className="network-empty">No POS terminals registered yet. Add each genuine till to calculate your estimate.</p>:data.terminals.map(terminal=><article className="billing-terminal" key={terminal.id}>
            <div><strong>{terminal.display_name}</strong><span>{terminal.branch_name?terminal.branch_name+" · ":""}{terminal.source==="connected_pos_feed"?"Detected from connected POS feed":"Manually registered"}</span></div>
            <div className="billing-terminal-actions"><span className={"billing-terminal-status "+terminal.status}>{terminal.status}</span><button type="button" className="network-secondary-button" onClick={()=>void setTerminalStatus(terminal.id,terminal.status==="active"?"inactive":"active")}>{terminal.status==="active"?"Deactivate":"Activate"}</button></div>
          </article>)}
        </div>
      </div>
      <div className="billing-payment-note"><strong>Subscription not activated</strong><p>{data.notice}</p><span>Online payments, invoices for subscriptions and automatic POS discovery will be added in later releases. No money is collected through this page.</span></div>
    </>}
  </section>;
}

type ReferralDashboardData = {
  referral_code: string;
  registered_referrals: number;
  payment_verified_referrals: number;
  required_referrals: number;
  remaining_to_qualify: number;
  discount_eligible: boolean;
  referrals: {id:string;business_name:string;status:string;created_at:string}[];
  reward_terms: {standard_price_per_pos_month:number;qualified_price_per_pos_month:number;payment_verification_available:boolean;note:string};
};

function ReferralWorkspace({session}:{session:AuthData}) {
  const [data,setData]=useState<ReferralDashboardData|null>(null);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");
  const [copied,setCopied]=useState(false);
  async function load() {
    setLoading(true); setError("");
    try {
      const response=await fetch(API_BASE+"/referrals/me",{headers:{Authorization:"Bearer "+session.access_token}});
      const result=await response.json();
      if(!response.ok) throw new Error(result.detail||"Could not load referral programme.");
      setData(result as ReferralDashboardData);
    } catch(err) {setError(err instanceof Error?err.message:"Could not load referral programme.");}
    finally {setLoading(false);}
  }
  useEffect(()=>{void load();},[session.access_token]);
  const referralLink=data ? window.location.origin+"/?ref="+encodeURIComponent(data.referral_code) : "";
  async function copyLink() {
    if(!referralLink) return;
    try {await navigator.clipboard.writeText(referralLink);setCopied(true);}
    catch {setError("Copy was blocked by this browser. Select and copy the referral link manually.");}
  }
  return <section className="finance-centre" id="referrals">
    <div className="profile-centre-heading"><div><div className="eyebrow">VEXION GROWTH PROGRAMME</div><h2>Refer businesses. Unlock lower POS pricing.</h2><p>Share your direct referral link. Your referred businesses appear here after they register.</p></div><span className="profile-status">Direct referrals only</span></div>
    {error && <p className="finance-alert" role="alert">{error}</p>}
    {loading ? <p className="network-empty">Loading your referral programme…</p> : data && <>
      <div className="finance-stats">
        <article><span>Businesses registered</span><strong>{data.registered_referrals}</strong><small>Direct referrals attributed to you</small></article>
        <article><span>Payments verified</span><strong>{data.payment_verified_referrals}</strong><small>Required to unlock the reward</small></article>
        <article><span>Still needed</span><strong>{data.remaining_to_qualify}</strong><small>Five paying businesses qualify</small></article>
        <article><span>Your POS price</span><strong>R {data.discount_eligible?399:499}</strong><small>Per active POS terminal / month</small></article>
      </div>
      <div className="finance-form">
        <h3>Your referral code</h3>
        <div className="finance-outstanding"><strong>{data.referral_code}</strong><button type="button" className="network-primary-button" onClick={()=>void copyLink()}>{copied?"Copied":"Copy referral link"}</button></div>
        <label>Share this link<input readOnly value={referralLink}/></label>
        <p className="finance-disclaimer">Reward rule: refer five separate businesses that become paying VEXION customers. Once verified, your subscription price becomes R399 per POS terminal per month instead of R499. This is a single-level programme; there are no downline commissions.</p>
        <p className="finance-alert">{data.reward_terms.note}</p>
      </div>
      <div className="finance-report"><div className="recruitment-card-heading"><div><span className="eyebrow">YOUR REFERRALS</span><h3>Businesses you've introduced</h3></div><span className="module-count">{data.referrals.length} TOTAL</span></div>
        {data.referrals.length===0?<p className="network-empty">No businesses have registered through your referral link yet.</p>:<div className="deal-file-list">{data.referrals.map(item=><article className="deal-file-card" key={item.id}><div className="deal-file-info"><strong>{item.business_name}</strong><span>Joined {new Date(item.created_at).toLocaleDateString("en-ZA")}</span></div><span className="quotation-status status-sent">{item.status.replaceAll("_"," ")}</span></article>)}</div>}
      </div>
    </>}
  </section>;
}



type InventoryItemRecord = { id:string; sku?:string|null; name:string; unit:string; reorder_level:string; is_active:boolean; stock_total:string; stock_by_location:Record<string,string>; below_reorder_level:boolean; negative_stock:boolean };
type InventoryMovementRecord = { id:string; item_name:string; movement_type:string; quantity_delta:string; location:string; source_type:string; unit_cost?:string|null; note?:string|null; created_at:string };
type InventoryProfitProduct = { inventory_item_id:string|null; sku:string|null; description:string; quantity_sold:string; line_revenue_before_transaction_discounts:string; costed_quantity:string; uncosted_quantity:string; cost_of_goods_sold:string|null; gross_profit_before_transaction_discounts:string|null; cost_status:string };
type InventoryProfitability = { period:{start:string;end_inclusive:string;timezone:string}; currency:string; sales_transaction_count:number; sales_line_count:number; refund_transaction_count:number; uncosted_line_count:number; uncosted_quantity:string; cost_of_goods_sold:string|null; cost_status:string; products:InventoryProfitProduct[]; limitations:string[] };

function InventoryWorkspace({session}:{session:AuthData}) {
  const [items,setItems]=useState<InventoryItemRecord[]>([]);
  const [movements,setMovements]=useState<InventoryMovementRecord[]>([]);
  const [profitability,setProfitability]=useState<InventoryProfitability|null>(null);
  const now=new Date();
  const localDate=(d:Date)=>new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,10);
  const [profitStart,setProfitStart]=useState(localDate(new Date(now.getFullYear(),now.getMonth(),1)));
  const [profitEnd,setProfitEnd]=useState(localDate(now));
  const [name,setName]=useState("");
  const [sku,setSku]=useState("");
  const [unit,setUnit]=useState("unit");
  const [reorder,setReorder]=useState("0");
  const [adjustments,setAdjustments]=useState<Record<string,{quantity:string;location:string;reason:string}>>({});
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");
  async function request(path:string,method="GET",body?:unknown) {
    const response=await fetch(API_BASE+path,{method,headers:{Authorization:"Bearer "+session.access_token,...(body?{"Content-Type":"application/json"}:{})},...(body?{body:JSON.stringify(body)}:{})});
    const data=await response.json().catch(()=>null);
    if(!response.ok)throw new Error(data?.detail||"Inventory request failed.");
    return data;
  }
  async function refresh() {
    try {
      const [itemRows,movementRows]=await Promise.all([request("/inventory/items"),request("/inventory/movements?limit=100")]);
      setItems(itemRows as InventoryItemRecord[]);setMovements(movementRows as InventoryMovementRecord[]);
    } catch(err){setError(err instanceof Error?err.message:"Could not load stock records.");}
  }
  async function loadProfitability() {
    try {
      const data=await request("/inventory/profitability?start_date="+encodeURIComponent(profitStart)+"&end_date="+encodeURIComponent(profitEnd));
      setProfitability(data as InventoryProfitability);
    } catch(err){setError(err instanceof Error?err.message:"Could not load inventory profitability.");}
  }
  useEffect(()=>{void refresh();void loadProfitability();},[session.access_token]);
  async function createItem(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();setBusy(true);setError("");setMessage("");
    try {
      await request("/inventory/items","POST",{name,sku:sku||null,unit,reorder_level:Number(reorder)});
      setName("");setSku("");setUnit("unit");setReorder("0");setMessage("Inventory item created. No opening stock has been assumed.");await refresh();
    } catch(err){setError(err instanceof Error?err.message:"Inventory item could not be created.");}
    finally{setBusy(false);}
  }
  function setAdjustment(itemId:string,key:"quantity"|"location"|"reason",value:string) {
    setAdjustments(current=>{const previous=current[itemId]||{quantity:"",location:"Main",reason:""};return {...current,[itemId]:{...previous,[key]:value}};});
  }
  async function adjust(item:InventoryItemRecord) {
    const draft=adjustments[item.id]||{quantity:"",location:"Main",reason:""};
    if(!draft.quantity||Number(draft.quantity)===0||!draft.reason.trim()){setError("Enter a non-zero quantity and a reason for the stock movement.");return;}
    setError("");setMessage("");
    try {
      await request("/inventory/items/"+item.id+"/adjustments","POST",{quantity_delta:Number(draft.quantity),location:draft.location||"Main",reason:draft.reason});
      setAdjustments(current=>({...current,[item.id]:{quantity:"",location:draft.location||"Main",reason:""}}));
      setMessage("Stock movement recorded for "+item.name+".");await refresh();await loadProfitability();
    } catch(err){setError(err instanceof Error?err.message:"Stock movement could not be recorded.");}
  }
  const fmt=(value:string)=>Number(value).toLocaleString("en-ZA",{minimumFractionDigits:3,maximumFractionDigits:3});
  return <section className="finance-centre" id="inventory-stock">
    <div className="profile-centre-heading"><div><div className="eyebrow">INVENTORY & STOCK CONTROL</div><h2>Know what is actually on hand.</h2><p>Stock is calculated from recorded movements, not estimates or assumed opening balances.</p></div><span className="profile-status">Movement-ledger stock</span></div>
    <p className="finance-alert">POS connections can send item-level SKUs and quantities. Matched sale items deduct stock automatically; totals-only feeds, unmapped SKUs and CSV imports without item lines do not. Refunds are not restocked automatically because returned goods must be verified.</p>
    {error&&<p className="finance-alert" role="alert">{error}</p>}{message&&<p className="finance-success" role="status">{message}</p>}
    <form className="finance-form" onSubmit={createItem}>
      <h3>Add inventory item</h3>
      <div className="finance-toolbar"><label>Item name<input required minLength={2} value={name} onChange={e=>setName(e.target.value)} placeholder="e.g. 2L cooking oil"/></label><label>SKU / barcode<input value={sku} onChange={e=>setSku(e.target.value)} placeholder="Optional unique code"/></label><label>Unit<input required value={unit} onChange={e=>setUnit(e.target.value)} placeholder="unit, kg, litre"/></label><label>Reorder level<input type="number" min="0" step="0.001" value={reorder} onChange={e=>setReorder(e.target.value)}/></label></div>
      <button className="network-primary-button" disabled={busy||!name.trim()||!unit.trim()}>{busy?"Saving…":"Create inventory item"}</button>
      <small>New items start with no stock movements. Record an opening balance only after physically verifying stock.</small>
    </form>
    <div className="finance-form">
      <div className="profile-centre-heading"><div><h3>Stock on hand</h3><p>{items.length} catalogue item(s). Quantities below are calculated from the stock ledger.</p></div><button type="button" className="network-secondary-button" onClick={()=>void refresh()}>Refresh</button></div>
      {items.length===0?<p className="network-empty">No inventory items have been created.</p>:items.map(item=><article className="purchase-order-card" key={item.id}>
        <div className="profile-centre-heading"><div><strong>{item.name}</strong><p>{item.sku||"No SKU"} · {item.unit} · Reorder at {fmt(item.reorder_level)}</p></div><span className="quotation-status status-sent">{item.is_active?"Active":"Inactive"}</span></div>
        <h3>{fmt(item.stock_total)} <small>{item.unit} recorded</small></h3>
        {item.negative_stock&&<p className="finance-alert">Recorded stock is negative. Review the opening count, POS item mapping and recent sales before making corrections.</p>}{item.below_reorder_level&&<p className="finance-alert">At or below the configured reorder level. Check actual stock before ordering.</p>}
        <div className="purchase-order-line"><span>Recorded by location</span><strong>{Object.keys(item.stock_by_location).length?Object.entries(item.stock_by_location).map(([location,qty])=>location+": "+fmt(qty)).join(" · "):"No stock movements recorded"}</strong></div>
        {item.is_active&&<div className="purchase-line-draft"><h4>Record verified stock movement</h4><div className="finance-toolbar"><label>Quantity change (+ or −)<input type="number" step="0.001" value={adjustments[item.id]?.quantity||""} onChange={e=>setAdjustment(item.id,"quantity",e.target.value)} placeholder="+10 or -2"/></label><label>Location<input value={adjustments[item.id]?.location||"Main"} onChange={e=>setAdjustment(item.id,"location",e.target.value)} /></label><label>Reason<input value={adjustments[item.id]?.reason||""} onChange={e=>setAdjustment(item.id,"reason",e.target.value)} placeholder="Opening count / damaged goods"/></label></div><button type="button" className="network-secondary-button" onClick={()=>void adjust(item)}>Record stock movement</button></div>}
      </article>)}
    </div>
    <div className="finance-form">
      <div className="profile-centre-heading"><div><h3>Product profitability & cost coverage</h3><p>Uses recorded purchase receipts and item-level POS sales. No missing cost is treated as zero.</p></div></div>
      <div className="finance-toolbar"><label>From<input type="date" value={profitStart} onChange={e=>setProfitStart(e.target.value)}/></label><label>To<input type="date" value={profitEnd} onChange={e=>setProfitEnd(e.target.value)}/></label><button type="button" className="network-primary-button" disabled={!profitStart||!profitEnd||profitEnd<profitStart} onClick={()=>void loadProfitability()}>Calculate profitability</button></div>
      {profitability&&<>
        <p className={profitability.cost_status==="complete"?"finance-success":"finance-alert"}>Cost coverage: {profitability.cost_status.replaceAll("_"," ")} · {profitability.sales_transaction_count} POS sale(s) · {profitability.uncosted_line_count} uncosted line(s) · {profitability.refund_transaction_count} refund(s) not reversed.</p>
        <div className="purchase-order-line"><span>Cost of goods sold</span><strong>{profitability.cost_of_goods_sold===null?"Not available — incomplete cost data":"R "+Number(profitability.cost_of_goods_sold).toLocaleString("en-ZA",{minimumFractionDigits:2,maximumFractionDigits:2})}</strong></div>
        {profitability.products.length===0?<p className="network-empty">No item-level POS sales were recorded in this period.</p>:profitability.products.map((product,index)=><article className="network-list-card" key={(product.inventory_item_id||product.sku||product.description)+"-"+index}>
          <strong>{product.description} · {product.sku||"No SKU"}</strong>
          <span>Qty {fmt(product.quantity_sold)} · Sales before transaction discounts R {product.line_revenue_before_transaction_discounts}</span>
          <span>COGS {product.cost_of_goods_sold===null?"Not available":"R "+product.cost_of_goods_sold} · Gross profit {product.gross_profit_before_transaction_discounts===null?"Not available":"R "+product.gross_profit_before_transaction_discounts}</span>
          <small>{product.cost_status.replaceAll("_"," ")}</small>
        </article>)}
        <details><summary>Costing limitations</summary>{profitability.limitations.map((item,index)=><p key={index}><small>{item}</small></p>)}</details>
      </>}
    </div>
    <div className="finance-form"><h3>Recent stock movement history</h3>{movements.length===0?<p className="network-empty">No stock movements have been recorded.</p>:movements.map(move=><article className="network-list-card" key={move.id}><strong>{move.item_name} · {move.quantity_delta}</strong><span>{move.movement_type.replaceAll("_"," ")} · {move.location} · {move.source_type}{move.unit_cost!==undefined&&move.unit_cost!==null?" · Unit cost R "+move.unit_cost:""}</span><small>{move.note||"No note"} · {new Date(move.created_at).toLocaleString("en-ZA")}</small></article>)}</div>
  </section>;
}

type SupplierRecord = { id:string; name:string; contact_name?:string|null; email?:string|null; phone?:string|null; is_active:boolean };
type PurchaseOrderLineRecord = { id:string; product_id?:string|null; description:string; quantity_ordered:string; quantity_received:string; quantity_outstanding:string; unit_price:string; tax_rate:string; line_total:string };
type PurchaseOrderRecord = { id:string; reference:string; supplier_id:string; supplier_name:string; status:string; expected_delivery_date?:string|null; subtotal:string; tax_total:string; total:string; lines:PurchaseOrderLineRecord[]; events?:{event_type:string;created_at:string;details:Record<string,unknown>}[] };
type PurchaseLineDraft = { description:string; product_id:string; quantity:string; unit_price:string; tax_rate:string };

function SupplierPurchasingWorkspace({session}:{session:AuthData}) {
  const [suppliers,setSuppliers]=useState<SupplierRecord[]>([]);
  const [inventoryItems,setInventoryItems]=useState<InventoryItemRecord[]>([]);
  const [receiptLocation,setReceiptLocation]=useState("Main");
  const [orders,setOrders]=useState<PurchaseOrderRecord[]>([]);
  const [supplierName,setSupplierName]=useState("");
  const [supplierContact,setSupplierContact]=useState("");
  const [supplierEmail,setSupplierEmail]=useState("");
  const [supplierPhone,setSupplierPhone]=useState("");
  const [selectedSupplier,setSelectedSupplier]=useState("");
  const [expectedDate,setExpectedDate]=useState("");
  const [orderNotes,setOrderNotes]=useState("");
  const [lines,setLines]=useState<PurchaseLineDraft[]>([{description:"",product_id:"",quantity:"1",unit_price:"",tax_rate:"15"}]);
  const [receiveQuantities,setReceiveQuantities]=useState<Record<string,string>>({});
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");

  async function request(path:string,method="GET",body?:unknown) {
    const response=await fetch(API_BASE+path,{method,headers:{Authorization:"Bearer "+session.access_token,...(body?{"Content-Type":"application/json"}:{})},...(body?{body:JSON.stringify(body)}:{})});
    const data=response.status===204?null:await response.json();
    if(!response.ok) throw new Error(data?.detail||"The procurement request failed.");
    return data;
  }
  async function refresh() {
    try {
      const [supplierRows,orderRows,itemRows]=await Promise.all([request("/procurement/suppliers"),request("/procurement/purchase-orders"),request("/inventory/items?active_only=true")]);
      setSuppliers(supplierRows as SupplierRecord[]);
      setInventoryItems(itemRows as InventoryItemRecord[]);
      setOrders(orderRows as PurchaseOrderRecord[]);
    } catch(err) { setError(err instanceof Error?err.message:"Could not load supplier and purchasing records."); }
  }
  useEffect(()=>{void refresh();},[session.access_token]);

  async function createSupplier(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();setBusy(true);setError("");setMessage("");
    try {
      const created=await request("/procurement/suppliers","POST",{name:supplierName,contact_name:supplierContact||null,email:supplierEmail||null,phone:supplierPhone||null}) as SupplierRecord;
      setSupplierName("");setSupplierContact("");setSupplierEmail("");setSupplierPhone("");setSelectedSupplier(created.id);
      setMessage("Supplier saved to this business workspace.");await refresh();
    } catch(err) {setError(err instanceof Error?err.message:"Supplier could not be saved.");}
    finally {setBusy(false);}
  }
  function updateLine(index:number,key:keyof PurchaseLineDraft,value:string) {
    setLines(current=>current.map((line,i)=>i===index?{...line,[key]:value}:line));
  }
  async function createOrder(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();setBusy(true);setError("");setMessage("");
    try {
      const created=await request("/procurement/purchase-orders","POST",{supplier_id:selectedSupplier,expected_delivery_date:expectedDate||null,notes:orderNotes||null,lines:lines.map(line=>({...line,product_id:line.product_id||null,quantity:Number(line.quantity),unit_price:Number(line.unit_price),tax_rate:Number(line.tax_rate)}))}) as PurchaseOrderRecord;
      setMessage("Draft "+created.reference+" created. Review it before submitting to the supplier.");
      setExpectedDate("");setOrderNotes("");setLines([{description:"",product_id:"",quantity:"1",unit_price:"",tax_rate:"15"}]);await refresh();
    } catch(err) {setError(err instanceof Error?err.message:"Purchase order could not be created.");}
    finally {setBusy(false);}
  }
  async function orderAction(order:PurchaseOrderRecord,action:"submit"|"cancel") {
    setError("");setMessage("");
    try {await request("/procurement/purchase-orders/"+order.id+"/"+action,"POST");setMessage(order.reference+" "+(action==="submit"?"submitted.":"cancelled."));await refresh();}
    catch(err){setError(err instanceof Error?err.message:"Purchase order action failed.");}
  }
  async function receiveLine(order:PurchaseOrderRecord,line:PurchaseOrderLineRecord) {
    const quantity=receiveQuantities[line.id]||"";
    if(!quantity||Number(quantity)<=0){setError("Enter the quantity actually received.");return;}
    setError("");setMessage("");
    try {
      await request("/procurement/purchase-orders/"+order.id+"/receive","POST",{lines:[{line_id:line.id,quantity:Number(quantity)}],location:receiptLocation,idempotency_key:crypto.randomUUID()});
      setReceiveQuantities(current=>({...current,[line.id]:""}));setMessage("Goods receipt recorded for "+order.reference+".");await refresh();
    } catch(err){setError(err instanceof Error?err.message:"Goods receipt could not be recorded.");}
  }
  const money=(value:string)=>"R "+Number(value).toLocaleString("en-ZA",{minimumFractionDigits:2,maximumFractionDigits:2});
  return <section className="finance-centre" id="supplier-purchasing">
    <div className="profile-centre-heading"><div><div className="eyebrow">SUPPLIERS & PURCHASING</div><h2>Control what your business orders.</h2><p>Maintain supplier records, prepare purchase orders and record quantities actually received.</p></div><span className="profile-status">Business-scoped records</span></div>
    <p className="finance-alert">Purchase orders are commitments, not paid expenses. Creating or receiving an order does not change income, expenses, stock or cash balances.</p>
    {error&&<p className="finance-alert" role="alert">{error}</p>}{message&&<p className="finance-success" role="status">{message}</p>}
    <div className="finance-layout">
      <form className="finance-form" onSubmit={createSupplier}>
        <h3>Add supplier</h3>
        <label>Supplier name<input required minLength={2} maxLength={180} value={supplierName} onChange={e=>setSupplierName(e.target.value)} placeholder="Supplier or company name"/></label>
        <label>Contact person<input value={supplierContact} onChange={e=>setSupplierContact(e.target.value)} placeholder="Contact name"/></label>
        <label>Email<input type="email" value={supplierEmail} onChange={e=>setSupplierEmail(e.target.value)} placeholder="accounts@supplier.co.za"/></label>
        <label>Phone<input value={supplierPhone} onChange={e=>setSupplierPhone(e.target.value)} placeholder="Supplier phone"/></label>
        <button className="network-primary-button" disabled={busy||!supplierName.trim()}>{busy?"Saving…":"Save supplier"}</button>
        <div className="network-list"><h3>Supplier directory · {suppliers.length}</h3>{suppliers.length===0?<p className="network-empty">No suppliers recorded yet.</p>:suppliers.map(s=><article className="network-list-card" key={s.id}><strong>{s.name}</strong><span>{s.contact_name||s.email||s.phone||"No contact details"}</span><small>{s.is_active?"Active":"Inactive"}</small></article>)}</div>
      </form>
      <form className="finance-form" onSubmit={createOrder}>
        <h3>Create purchase order</h3>
        <label>Supplier<select required value={selectedSupplier} onChange={e=>setSelectedSupplier(e.target.value)}><option value="">Choose supplier</option>{suppliers.filter(s=>s.is_active).map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
        <label>Expected delivery date<input type="date" value={expectedDate} onChange={e=>setExpectedDate(e.target.value)}/></label>
        <label>Notes<textarea value={orderNotes} onChange={e=>setOrderNotes(e.target.value)} rows={2} placeholder="Delivery instructions or internal notes"/></label>
        <label>Stock location for receipts<input value={receiptLocation} onChange={e=>setReceiptLocation(e.target.value)} placeholder="Main"/></label><h4>Order lines</h4>
        {lines.map((line,index)=><div className="purchase-line-draft" key={index}>
          <label>Link inventory item (optional)<select value={line.product_id} onChange={e=>updateLine(index,"product_id",e.target.value)}><option value="">Do not track stock for this line</option>{inventoryItems.map(item=><option key={item.id} value={item.id}>{item.name}{item.sku?" · "+item.sku:""}</option>)}</select></label><label>Description<input required value={line.description} onChange={e=>updateLine(index,"description",e.target.value)} placeholder="Item or service"/></label>
          <div className="finance-toolbar"><label>Qty<input type="number" min="0.001" step="0.001" required value={line.quantity} onChange={e=>updateLine(index,"quantity",e.target.value)}/></label><label>Unit price (R)<input type="number" min="0" step="0.01" required value={line.unit_price} onChange={e=>updateLine(index,"unit_price",e.target.value)}/></label><label>VAT %<input type="number" min="0" max="100" step="0.01" value={line.tax_rate} onChange={e=>updateLine(index,"tax_rate",e.target.value)}/></label></div>
          {lines.length>1&&<button type="button" className="network-secondary-button" onClick={()=>setLines(current=>current.filter((_,i)=>i!==index))}>Remove line</button>}
        </div>)}
        <button type="button" className="network-secondary-button" onClick={()=>setLines(current=>[...current,{description:"",product_id:"",quantity:"1",unit_price:"",tax_rate:"15"}])}>Add another line</button>
        <button className="network-primary-button" disabled={busy||!selectedSupplier||lines.some(line=>!line.description.trim()||!line.unit_price)}>{busy?"Saving…":"Save draft purchase order"}</button>
      </form>
    </div>
    <div className="finance-form">
      <div className="profile-centre-heading"><div><h3>Purchase orders</h3><p>{orders.length} recorded order(s). Submit drafts only after checking quantities and prices.</p></div><button type="button" className="network-secondary-button" onClick={()=>void refresh()}>Refresh</button></div>
      {orders.length===0?<p className="network-empty">No purchase orders recorded yet.</p>:orders.map(order=><article className="purchase-order-card" key={order.id}>
        <div className="profile-centre-heading"><div><strong>{order.reference}</strong><p>{order.supplier_name} · {order.expected_delivery_date||"No delivery date"}</p></div><span className="quotation-status status-sent">{order.status.replaceAll("_"," ")}</span></div>
        <p><strong>{money(order.total)}</strong> <small>incl. VAT · {order.lines.length} line(s)</small></p>
        {order.lines.map(line=><div className="purchase-order-line" key={line.id}><span>{line.description}<small>{line.product_id?"Stock-tracked item":"Not linked to stock"} · Ordered {line.quantity_ordered} · Received {line.quantity_received} · Outstanding {line.quantity_outstanding}</small></span><strong>{money(line.line_total)}</strong>
          {(order.status==="submitted"||order.status==="partially_received")&&Number(line.quantity_outstanding)>0&&<div className="finance-toolbar"><input aria-label={"Quantity received for "+line.description} type="number" min="0.001" max={line.quantity_outstanding} step="0.001" placeholder="Qty received" value={receiveQuantities[line.id]||""} onChange={e=>setReceiveQuantities(current=>({...current,[line.id]:e.target.value}))}/><button type="button" className="network-secondary-button" onClick={()=>void receiveLine(order,line)}>Record receipt</button></div>}
        </div>)}
        {order.status==="draft"&&<button type="button" className="network-primary-button" onClick={()=>void orderAction(order,"submit")}>Submit purchase order</button>}
        {(order.status==="draft"||order.status==="submitted")&&<button type="button" className="network-secondary-button" onClick={()=>void orderAction(order,"cancel")}>Cancel order</button>}
        {order.events&&<details><summary>Order audit history</summary>{order.events.map((event,index)=><p key={index}><small>{new Date(event.created_at).toLocaleString("en-ZA")} · {event.event_type.replaceAll("_"," ")}</small></p>)}</details>}
      </article>)}
    </div>
  </section>;
}

type SupplierInvoiceRecord = {id:string;supplier_id:string;supplier_name:string;purchase_order_id:string|null;supplier_reference:string;invoice_date:string;due_date:string|null;currency:string;subtotal:string;tax_total:string;total:string;status:string;match_results:{flags:{code:string;severity:string;message:string}[];line_results:{description:string;flags:string[]}[];flag_count:number};events?:{event_type:string;created_at:string}[]};
type SupplierInvoiceDraftLine = {description:string;purchase_order_line_id:string;quantity:string;unit_price:string;tax_rate:string};

function SupplierInvoiceMatchingWorkspace({session}:{session:AuthData}) {
  const [suppliers,setSuppliers]=useState<SupplierRecord[]>([]);
  const [orders,setOrders]=useState<PurchaseOrderRecord[]>([]);
  const [invoices,setInvoices]=useState<SupplierInvoiceRecord[]>([]);
  const [supplierId,setSupplierId]=useState("");
  const [orderId,setOrderId]=useState("");
  const [reference,setReference]=useState("");
  const [invoiceDate,setInvoiceDate]=useState(new Date().toISOString().slice(0,10));
  const [dueDate,setDueDate]=useState("");
  const [subtotal,setSubtotal]=useState("");
  const [taxTotal,setTaxTotal]=useState("");
  const [total,setTotal]=useState("");
  const [notes,setNotes]=useState("");
  const [lines,setLines]=useState<SupplierInvoiceDraftLine[]>([{description:"",purchase_order_line_id:"",quantity:"1",unit_price:"",tax_rate:"15"}]);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");
  async function request(path:string,method="GET",body?:unknown) {
    const response=await fetch(API_BASE+path,{method,headers:{Authorization:"Bearer "+session.access_token,...(body?{"Content-Type":"application/json"}:{})},...(body?{body:JSON.stringify(body)}:{})});
    const data=await response.json().catch(()=>null);
    if(!response.ok)throw new Error(data?.detail||"Supplier invoice request failed.");
    return data;
  }
  async function refresh() {
    try {
      const [supplierRows,orderRows,invoiceRows]=await Promise.all([request("/procurement/suppliers?active_only=true"),request("/procurement/purchase-orders"),request("/supplier-invoices")]);
      setSuppliers(supplierRows as SupplierRecord[]);setOrders(orderRows as PurchaseOrderRecord[]);setInvoices(invoiceRows as SupplierInvoiceRecord[]);
    } catch(err){setError(err instanceof Error?err.message:"Could not load supplier invoices.");}
  }
  useEffect(()=>{void refresh();},[session.access_token]);
  const selectedOrder=orders.find(o=>o.id===orderId);
  function updateLine(index:number,key:keyof SupplierInvoiceDraftLine,value:string){setLines(current=>current.map((line,i)=>i===index?{...line,[key]:value}:line));}
  async function createInvoice(event:FormEvent<HTMLFormElement>){
    event.preventDefault();setBusy(true);setError("");setMessage("");
    try{
      const created=await request("/supplier-invoices","POST",{
        supplier_id:supplierId,purchase_order_id:orderId||null,supplier_reference:reference,invoice_date:invoiceDate,due_date:dueDate||null,currency:"ZAR",
        stated_subtotal:Number(subtotal),stated_tax_total:Number(taxTotal),stated_total:Number(total),notes:notes||null,
        lines:lines.map(line=>({...line,purchase_order_line_id:line.purchase_order_line_id||null,quantity:Number(line.quantity),unit_price:Number(line.unit_price),tax_rate:Number(line.tax_rate)}))
      }) as SupplierInvoiceRecord;
      setMessage("Invoice "+created.supplier_reference+" captured. "+created.match_results.flag_count+" matching flag(s) require review.");
      setReference("");setSubtotal("");setTaxTotal("");setTotal("");setNotes("");setLines([{description:"",purchase_order_line_id:"",quantity:"1",unit_price:"",tax_rate:"15"}]);await refresh();
    }catch(err){setError(err instanceof Error?err.message:"Supplier invoice could not be saved.");}
    finally{setBusy(false);}
  }
  async function approve(invoice:SupplierInvoiceRecord){
    const reason=invoice.match_results.flag_count?window.prompt("This invoice has matching flags. Enter the documented manager override reason (at least 8 characters):"):"";
    if(invoice.match_results.flag_count&&(!reason||reason.trim().length<8))return;
    setError("");setMessage("");
    try{await request("/supplier-invoices/"+invoice.id+"/approve","POST",{override_reason:reason||null});setMessage(invoice.supplier_reference+" approved. No payment or ledger posting was initiated.");await refresh();}
    catch(err){setError(err instanceof Error?err.message:"Invoice approval failed.");}
  }
  const money=(value:string)=>"R "+Number(value).toLocaleString("en-ZA",{minimumFractionDigits:2,maximumFractionDigits:2});
  return <section className="finance-centre" id="supplier-invoice-matching">
    <div className="profile-centre-heading"><div><div className="eyebrow">SUPPLIER INVOICE CONTROL</div><h2>Check every supplier bill before approval.</h2><p>Compare billed quantities and prices with purchase orders and goods actually received.</p></div><span className="profile-status">Review & audit trail</span></div>
    <p className="finance-alert">Capturing or approving a supplier invoice does not pay the supplier or automatically post an expense, VAT claim or inventory cost. Those actions remain separate.</p>
    {error&&<p className="finance-alert" role="alert">{error}</p>}{message&&<p className="finance-success" role="status">{message}</p>}
    <div className="finance-layout">
      <form className="finance-form" onSubmit={createInvoice}>
        <h3>Capture supplier invoice</h3>
        <label>Supplier<select required value={supplierId} onChange={e=>{setSupplierId(e.target.value);setOrderId("");}}><option value="">Choose supplier</option>{suppliers.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
        <label>Purchase order (recommended)<select value={orderId} onChange={e=>{setOrderId(e.target.value);const po=orders.find(o=>o.id===e.target.value);if(po&&po.supplier_id!==supplierId)setSupplierId(po.supplier_id);}}><option value="">No purchase order</option>{orders.filter(o=>!supplierId||o.supplier_id===supplierId).map(o=><option key={o.id} value={o.id}>{o.reference} · {o.status}</option>)}</select></label>
        <label>Supplier invoice reference<input required value={reference} onChange={e=>setReference(e.target.value)} placeholder="Supplier's invoice number"/></label>
        <div className="finance-toolbar"><label>Invoice date<input type="date" required value={invoiceDate} onChange={e=>setInvoiceDate(e.target.value)}/></label><label>Due date<input type="date" value={dueDate} onChange={e=>setDueDate(e.target.value)}/></label></div>
        <h4>Invoice lines</h4>
        {lines.map((line,index)=><div className="purchase-line-draft" key={index}>
          <label>Match purchase order line<select value={line.purchase_order_line_id} onChange={e=>{const poLine=selectedOrder?.lines.find(x=>x.id===e.target.value);setLines(current=>current.map((v,i)=>i===index?{...v,purchase_order_line_id:e.target.value,description:poLine?.description||v.description,unit_price:poLine?.unit_price||v.unit_price,tax_rate:poLine?.tax_rate||v.tax_rate}:v));}}><option value="">Unmatched / no PO line</option>{selectedOrder?.lines.map(x=><option key={x.id} value={x.id}>{x.description} · received {x.quantity_received}/{x.quantity_ordered}</option>)}</select></label>
          <label>Description<input required value={line.description} onChange={e=>updateLine(index,"description",e.target.value)} placeholder="Invoice line description"/></label>
          <div className="finance-toolbar"><label>Qty billed<input type="number" min="0.001" step="0.001" required value={line.quantity} onChange={e=>updateLine(index,"quantity",e.target.value)}/></label><label>Unit price (R)<input type="number" min="0" step="0.01" required value={line.unit_price} onChange={e=>updateLine(index,"unit_price",e.target.value)}/></label><label>VAT %<input type="number" min="0" max="100" step="0.01" value={line.tax_rate} onChange={e=>updateLine(index,"tax_rate",e.target.value)}/></label></div>
          {lines.length>1&&<button type="button" className="network-secondary-button" onClick={()=>setLines(current=>current.filter((_,i)=>i!==index))}>Remove line</button>}
        </div>)}
        <button type="button" className="network-secondary-button" onClick={()=>setLines(current=>[...current,{description:"",purchase_order_line_id:"",quantity:"1",unit_price:"",tax_rate:"15"}])}>Add invoice line</button>
        <h4>Amounts as printed on supplier invoice</h4>
        <div className="finance-toolbar"><label>Subtotal (R)<input type="number" min="0" step="0.01" required value={subtotal} onChange={e=>setSubtotal(e.target.value)}/></label><label>VAT total (R)<input type="number" min="0" step="0.01" required value={taxTotal} onChange={e=>setTaxTotal(e.target.value)}/></label><label>Total (R)<input type="number" min="0" step="0.01" required value={total} onChange={e=>setTotal(e.target.value)}/></label></div>
        <label>Internal notes<textarea rows={2} value={notes} onChange={e=>setNotes(e.target.value)}/></label>
        <button className="network-primary-button" disabled={busy||!supplierId||!reference.trim()||lines.some(x=>!x.description.trim()||!x.unit_price)}>{busy?"Saving…":"Capture & match invoice"}</button>
      </form>
      <div className="finance-form">
        <div className="profile-centre-heading"><div><h3>Invoice review queue</h3><p>{invoices.filter(x=>x.status==="needs_review").length} awaiting approval · {invoices.length} total</p></div><button type="button" className="network-secondary-button" onClick={()=>void refresh()}>Refresh</button></div>
        {invoices.length===0?<p className="network-empty">No supplier invoices recorded yet.</p>:invoices.map(invoice=><article className="purchase-order-card" key={invoice.id}>
          <div className="profile-centre-heading"><div><strong>{invoice.supplier_name} · {invoice.supplier_reference}</strong><p>{invoice.invoice_date} · {money(invoice.total)}</p></div><span className="profile-status">{invoice.status.replaceAll("_"," ")}</span></div>
          <p>{invoice.match_results.flag_count===0?"No matching differences detected.":invoice.match_results.flag_count+" matching flag(s) need review."}</p>
          {invoice.match_results.flags?.map((flag,index)=><p className="finance-alert" key={index}><strong>{flag.code.replaceAll("_"," ")}</strong> · {flag.message}</p>)}
          {invoice.status==="needs_review"&&<button type="button" className="network-primary-button" onClick={()=>void approve(invoice)}>Review & approve</button>}
        </article>)}
      </div>
    </div>
  </section>;
}


type SupplierPayable = {id:string;invoice_id:string;supplier_id:string;supplier_name:string;supplier_reference:string;currency:string;total_amount:string;amount_paid:string;balance_due:string;due_date:string|null;status:string;payments:{id:string;amount:string;payment_date:string;payment_method:string;reference:string|null}[]};
function SupplierPayablesWorkspace({session}:{session:AuthData}) {
  const [rows,setRows]=useState<SupplierPayable[]>([]);
  const [amounts,setAmounts]=useState<Record<string,string>>({});
  const [references,setReferences]=useState<Record<string,string>>({});
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");
  async function request(path:string,method="GET",body?:unknown) {
    const response=await fetch(API_BASE+path,{method,headers:{Authorization:"Bearer "+session.access_token,...(body?{"Content-Type":"application/json"}:{})},...(body?{body:JSON.stringify(body)}:{})});
    const data=await response.json().catch(()=>null);
    if(!response.ok)throw new Error(data?.detail||"Accounts payable request failed.");
    return data;
  }
  async function refresh(){try{setRows(await request("/supplier-invoices/payables/list") as SupplierPayable[]);}catch(e){setError(e instanceof Error?e.message:"Could not load supplier payables.");}}
  useEffect(()=>{void refresh();},[session.access_token]);
  async function recordPayment(row:SupplierPayable){
    const amount=amounts[row.invoice_id]||"";
    if(!amount||Number(amount)<=0)return;
    setBusy(true);setError("");setMessage("");
    try{
      const key=window.crypto?.randomUUID?.()||("vexion-"+Date.now()+"-"+Math.random().toString(36).slice(2));
      const paymentDate=new Intl.DateTimeFormat("en-CA",{timeZone:"Africa/Johannesburg"}).format(new Date());
      const result=await request("/supplier-invoices/"+row.invoice_id+"/payments","POST",{
        amount:Number(amount),payment_date:paymentDate,payment_method:"manual",
        reference:references[row.invoice_id]||null,idempotency_key:key
      });
      setMessage("Payment recorded. Outstanding balance: R "+result.payable.balance_due+". This is a manual record, not bank verification.");
      setAmounts(current=>({...current,[row.invoice_id]:""}));await refresh();
    }catch(e){setError(e instanceof Error?e.message:"Payment could not be recorded.");}
    finally{setBusy(false);}
  }
  const money=(v:string)=>"R "+Number(v).toLocaleString("en-ZA",{minimumFractionDigits:2,maximumFractionDigits:2});
  return <section className="finance-centre" id="supplier-payables">
    <div className="profile-centre-heading"><div><div className="eyebrow">ACCOUNTS PAYABLE</div><h2>Know exactly what your business still owes.</h2><p>Approved supplier invoices become liabilities. Record full or partial payments and keep the remaining balance visible.</p></div><span className="profile-status">Payment ledger</span></div>
    <p className="finance-alert">Payments entered here are manually recorded, not confirmed by your bank. This ledger does not automatically create expense entries or stock movements. Goods received remain recorded through the purchase-order receiving process.</p>
    {error&&<p className="finance-alert" role="alert">{error}</p>}{message&&<p className="finance-success" role="status">{message}</p>}
    <div className="finance-form"><div className="profile-centre-heading"><h3>Outstanding supplier balances</h3><button className="network-secondary-button" type="button" onClick={()=>void refresh()}>Refresh</button></div>
    {!rows.length?<p className="network-empty">No approved supplier payables yet.</p>:rows.map(row=><article className="purchase-order-card" key={row.id}>
      <div className="profile-centre-heading"><div><strong>{row.supplier_name} · {row.supplier_reference}</strong><p>{money(row.total_amount)} total · Due {row.due_date||"date not specified"} · Paid {money(row.amount_paid)}</p></div><span className="profile-status">{row.status.replaceAll("_"," ")}</span></div>
      <h3>Outstanding: {money(row.balance_due)}</h3>
      {row.payments.map(p=><p key={p.id}>Payment {money(p.amount)} · {p.payment_date} · {p.payment_method}{p.reference?" · "+p.reference:""}</p>)}
      {row.status!=="paid"&&<div className="finance-toolbar"><label>Payment amount (R)<input type="number" min="0.01" max={row.balance_due} step="0.01" value={amounts[row.invoice_id]||""} onChange={e=>setAmounts(v=>({...v,[row.invoice_id]:e.target.value}))}/></label><label>Payment reference<input value={references[row.invoice_id]||""} onChange={e=>setReferences(v=>({...v,[row.invoice_id]:e.target.value}))} placeholder="Optional bank / cash reference"/></label><button className="network-primary-button" type="button" disabled={busy||!amounts[row.invoice_id]||Number(amounts[row.invoice_id])>Number(row.balance_due)} onClick={()=>void recordPayment(row)}>Record payment</button></div>}
    </article>)}</div>
  </section>;
}


export default function App() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");
  const [session, setSession] = useState<AuthData | null>(readSession);
  const [mode, setMode] = useState<"register" | "login">("register");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [businessName, setBusinessName] = useState("");
  const [industry, setIndustry] = useState("");
  const [country, setCountry] = useState("ZA");
  const [referralCode, setReferralCode] = useState(() => new URLSearchParams(window.location.search).get("ref")?.toUpperCase() ?? "");
  const [profileImage, setProfileImage] = useState<string | null>(null);
  const [imageError, setImageError] = useState("");
  const [profileDraft, setProfileDraft] = useState<BusinessProfile>(() => ({
    name: session?.business.name ?? "", industry: session?.business.industry ?? "", country: session?.business.country ?? "ZA",
    registration_number: session?.business.registration_number ?? "", website: session?.business.website ?? "",
    contact_email: session?.business.contact_email ?? "", phone: session?.business.phone ?? "",
    address_line: session?.business.address_line ?? "", city: session?.business.city ?? "",
    province: session?.business.province ?? "", postal_code: session?.business.postal_code ?? "",
    description: session?.business.description ?? "", profile_image_data_url: session?.business.profile_image_data_url ?? null,
    directory_listed: session?.business.directory_listed ?? false, public_email: session?.business.public_email ?? false,
    public_phone: session?.business.public_phone ?? false, public_website: session?.business.public_website ?? false,
    public_location: session?.business.public_location ?? false,
  }));
  const [profileBusy, setProfileBusy] = useState(false);
  const [profileMessage, setProfileMessage] = useState("");
  const [directoryResults, setDirectoryResults] = useState<PublicBusiness[]>([]);
  const [directoryQuery, setDirectoryQuery] = useState("");
  const [directoryBusy, setDirectoryBusy] = useState(false);
  const [directoryMessage, setDirectoryMessage] = useState("");
  const [incomingInvitations, setIncomingInvitations] = useState<NetworkInvitation[]>([]);
  const [conversations, setConversations] = useState<NetworkConversation[]>([]);
  const [selectedConversation, setSelectedConversation] = useState<NetworkConversation | null>(null);
  const [conversationMessages, setConversationMessages] = useState<NetworkMessage[]>([]);
  const [dealRoomMessages, setDealRoomMessages] = useState<NetworkMessage[]>([]);
  const [dealRoom, setDealRoom] = useState<DealRoom | null>(null);
  const [quotations, setQuotations] = useState<Quotation[]>([]);
  const [dealFiles, setDealFiles] = useState<DealFile[]>([]);
  const [selectedDealFile, setSelectedDealFile] = useState<File | null>(null);
  const [fileBusy, setFileBusy] = useState(false);
  const [fileMessage, setFileMessage] = useState("");
  const [quoteTitle, setQuoteTitle] = useState("");
  const [quoteCurrency, setQuoteCurrency] = useState("ZAR");
  const [quoteValidUntil, setQuoteValidUntil] = useState("");
  const [quoteNotes, setQuoteNotes] = useState("");
  const [quoteLines, setQuoteLines] = useState<QuoteLineDraft[]>([{description:"",quantity:"1",unit_price:"",tax_rate:"15"}]);
  const [inviteTarget, setInviteTarget] = useState<PublicBusiness | null>(null);
  const [invitePassword, setInvitePassword] = useState("");
  const [inviteMessage, setInviteMessage] = useState("");
  const [acceptPassword, setAcceptPassword] = useState("");
  const [conversationDraft, setConversationDraft] = useState("");
  const [dealDraft, setDealDraft] = useState("");
  const [networkActionBusy, setNetworkActionBusy] = useState(false);
  const [networkActionMessage, setNetworkActionMessage] = useState("");
  const [jobs, setJobs] = useState<any[]>([]);
  const [applications, setApplications] = useState<any[]>([]);
  const [jobTitle, setJobTitle] = useState("");
  const [jobDepartment, setJobDepartment] = useState("");
  const [jobLocation, setJobLocation] = useState("");
  const [jobType, setJobType] = useState("full_time");
  const [jobDescription, setJobDescription] = useState("");
  const [jobRequirements, setJobRequirements] = useState("");
  const [recruitmentBusy, setRecruitmentBusy] = useState(false);
  const [recruitmentMessage, setRecruitmentMessage] = useState("");
  const [staff, setStaff] = useState<any[]>([]);
  const [staffInvitations, setStaffInvitations] = useState<any[]>([]);
  const [staffPhone, setStaffPhone] = useState("");
  const [staffWhatsAppUrl, setStaffWhatsAppUrl] = useState("");
  const [staffRole, setStaffRole] = useState("employee");
  const [staffMessage, setStaffMessage] = useState("");
  const [staffBusy, setStaffBusy] = useState(false);
  const [staffAcceptBusy, setStaffAcceptBusy] = useState(false);
  const [staffAcceptMessage, setStaffAcceptMessage] = useState("");
  const [staffAcceptName, setStaffAcceptName] = useState("");
    const [staffAcceptPassword, setStaffAcceptPassword] = useState("");
  const staffInviteToken = new URLSearchParams(window.location.search).get("staff_invite") ?? "";
  async function refreshStaff() { if (!session) return; try { const [members, invites] = await Promise.all([networkRequest("/staff"), networkRequest("/staff/invitations")]); setStaff(members); setStaffInvitations(invites); } catch (err) { setStaffMessage(err instanceof Error ? err.message : "Could not load staff."); } }
  useEffect(() => { if (session) void refreshStaff(); }, [session?.access_token]);
  async function inviteStaff(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setStaffBusy(true); setStaffMessage(""); setStaffWhatsAppUrl(""); try { const result = await networkRequest("/staff/invitations", "POST", { phone: staffPhone, role: staffRole }); const text = `You have been invited to join ${session?.business.name} on VEXION as ${staffRole}. Accept your secure invitation here (expires in 48 hours): ${result.invite_url}`; setStaffWhatsAppUrl("https://wa.me/" + result.phone + "?text=" + encodeURIComponent(text)); setStaffPhone(""); setStaffMessage("Invitation created. Open WhatsApp to send it to your team member."); await refreshStaff(); } catch (err) { setStaffMessage(err instanceof Error ? err.message : "Invitation could not be created."); } finally { setStaffBusy(false); } }
  async function changeStaffRole(id: string, role: string) { try { await networkRequest("/staff/" + id, "PATCH", { role }); await refreshStaff(); } catch (err) { setStaffMessage(err instanceof Error ? err.message : "Role could not be changed."); } }
  async function removeStaff(id: string) { if (!window.confirm("Remove this staff member access to the business?")) return; try { await networkRequest("/staff/" + id, "DELETE"); await refreshStaff(); } catch (err) { setStaffMessage(err instanceof Error ? err.message : "Staff member could not be removed."); } }
  const [applicantFilter, setApplicantFilter] = useState("all");



  async function refreshRecruitment() {
    if (!session) return;
    try { const [jobData, applicantData] = await Promise.all([networkRequest("/recruitment/jobs"), networkRequest("/recruitment/applications")]); setJobs(jobData); setApplications(applicantData); }
    catch (err) { setRecruitmentMessage(err instanceof Error ? err.message : "Could not load recruitment records."); }
  }
  useEffect(() => { if (session) void refreshRecruitment(); }, [session?.access_token]);
  async function createJob(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setRecruitmentBusy(true); setRecruitmentMessage("");
    try { await networkRequest("/recruitment/jobs", "POST", { title: jobTitle, department: jobDepartment || null, location: jobLocation || null, employment_type: jobType, description: jobDescription, requirements: jobRequirements || null, status: "published" }); setJobTitle(""); setJobDepartment(""); setJobLocation(""); setJobDescription(""); setJobRequirements(""); setRecruitmentMessage("Vacancy published to your recruitment workspace."); await refreshRecruitment(); }
    catch (err) { setRecruitmentMessage(err instanceof Error ? err.message : "Vacancy could not be created."); } finally { setRecruitmentBusy(false); }
  }
  async function changeJobStatus(jobId: string, status: string) {
    try { await networkRequest("/recruitment/jobs/" + jobId, "PATCH", { status }); await refreshRecruitment(); }
    catch (err) { setRecruitmentMessage(err instanceof Error ? err.message : "Vacancy status could not be changed."); }
  }
  async function changeApplicantStatus(applicationId: string, status: string) {
    try { await networkRequest("/recruitment/applications/" + applicationId, "PATCH", { status }); await refreshRecruitment(); }
    catch (err) { setRecruitmentMessage(err instanceof Error ? err.message : "Applicant status could not be changed."); }
  }

  function handleProfileImage(file?: File) {
    setImageError("");
    if (!file) { setProfileImage(null); return; }
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) { setImageError("Choose a JPG, PNG or WebP image."); return; }
    if (file.size > 2 * 1024 * 1024) { setImageError("The image must be 2 MB or smaller."); return; }
    const reader = new FileReader();
    reader.onload = () => { const image = typeof reader.result === "string" ? reader.result : null; setProfileImage(image); setProfileDraft(current => ({ ...current, profile_image_data_url: image })); };
    reader.onerror = () => setImageError("Image could not be read. Please try another file.");
    reader.readAsDataURL(file);
  }

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_BASE}/health`, { signal: controller.signal })
      .then((response) => { if (!response.ok) throw new Error("API unavailable"); return response.json(); })
      .then(() => setApiStatus("online"))
      .catch(() => { if (!controller.signal.aborted) setApiStatus("offline"); });
    return () => controller.abort();
  }, []);

  async function networkRequest(path: string, method = "GET", body?: unknown) {
    if (!session) throw new Error("Please sign in again.");
    const response = await fetch(API_BASE + path, {
      method, headers: { Authorization: "Bearer " + session.access_token, ...(body ? { "Content-Type": "application/json" } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "The Business Network request failed.");
    return data;
  }

  async function refreshNetwork() {
    if (!session) return;
    try {
      const [invites, chats] = await Promise.all([
        networkRequest("/network/invitations?direction=incoming"),
        networkRequest("/network/conversations"),
      ]);
      setIncomingInvitations(invites as NetworkInvitation[]);
      setConversations(chats as NetworkConversation[]);
    } catch (err) {
      setNetworkActionMessage(err instanceof Error ? err.message : "Could not refresh conversations.");
    }
  }

  useEffect(() => { if (session) void refreshNetwork(); }, [session?.access_token]);

  useEffect(() => {
    if (!session || !selectedConversation) { setConversationMessages([]); setDealRoomMessages([]); setDealRoom(null); setDealFiles([]); return; }
    let cancelled = false;
    async function loadMessages() {
      try {
        const messages = await networkRequest("/network/conversations/" + selectedConversation!.id + "/messages");
        if (!cancelled) setConversationMessages(messages as NetworkMessage[]);
        if (selectedConversation!.deal_room_id) {
          const room = { id: selectedConversation!.deal_room_id, conversation_id: selectedConversation!.id, status: selectedConversation!.deal_room_status ?? "discussion", created_at: "", updated_at: "" };
          const dealMessages = await networkRequest("/network/deal-rooms/" + room.id + "/messages");
          const dealQuotes = await networkRequest("/network/deal-rooms/" + room.id + "/quotations");
          if (!cancelled) { setDealRoom(room); setDealRoomMessages(dealMessages as NetworkMessage[]); setQuotations(dealQuotes as Quotation[]); }
        } else if (!cancelled) { setDealRoom(null); setDealRoomMessages([]); setQuotations([]); setDealFiles([]); }
      } catch (err) { if (!cancelled) setNetworkActionMessage(err instanceof Error ? err.message : "Could not load messages."); }
    }
    void loadMessages();
    return () => { cancelled = true; };
  }, [session?.access_token, selectedConversation?.id, selectedConversation?.deal_room_id]);

  async function sendBusinessInvitation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!inviteTarget) return;
    setNetworkActionBusy(true); setNetworkActionMessage("");
    try {
      await networkRequest("/network/invitations", "POST", { invited_business_id: inviteTarget.id, invitation_message: inviteMessage, access_password: invitePassword });
      setNetworkActionMessage("Invitation sent. Share the password separately with the invited business contact.");
      setInviteTarget(null); setInvitePassword(""); setInviteMessage(""); await refreshNetwork();
    } catch (err) { setNetworkActionMessage(err instanceof Error ? err.message : "Could not send invitation."); }
    finally { setNetworkActionBusy(false); }
  }

  async function acceptBusinessInvitation(invitationId: string) {
    setNetworkActionBusy(true); setNetworkActionMessage("");
    try {
      const conversation = await networkRequest("/network/invitations/" + invitationId + "/accept", "POST", { access_password: acceptPassword }) as NetworkConversation;
      setAcceptPassword(""); setSelectedConversation(conversation);
      setNetworkActionMessage("Invitation accepted. Your private conversation is ready."); await refreshNetwork();
    } catch (err) { setNetworkActionMessage(err instanceof Error ? err.message : "Could not accept invitation."); }
    finally { setNetworkActionBusy(false); }
  }

  async function rejectBusinessInvitation(invitationId: string) {
    setNetworkActionBusy(true); setNetworkActionMessage("");
    try { await networkRequest("/network/invitations/" + invitationId + "/reject", "POST"); await refreshNetwork(); setNetworkActionMessage("Invitation declined."); }
    catch (err) { setNetworkActionMessage(err instanceof Error ? err.message : "Could not decline invitation."); }
    finally { setNetworkActionBusy(false); }
  }

  async function sendConversationMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedConversation || !conversationDraft.trim()) return;
    try {
      await networkRequest("/network/conversations/" + selectedConversation.id + "/messages", "POST", { body: conversationDraft });
      setConversationDraft("");
      const messages = await networkRequest("/network/conversations/" + selectedConversation.id + "/messages");
      setConversationMessages(messages as NetworkMessage[]);
    } catch (err) { setNetworkActionMessage(err instanceof Error ? err.message : "Message could not be sent."); }
  }

  async function openDealRoom() {
    if (!selectedConversation) return;
    try {
      const room = await networkRequest("/network/conversations/" + selectedConversation.id + "/deal-room", "POST") as DealRoom;
      setDealRoom(room);
      const updated = { ...selectedConversation, deal_room_id: room.id, deal_room_status: room.status };
      setSelectedConversation(updated);
      setConversations(current => current.map(item => item.id === updated.id ? updated : item));
      setDealRoomMessages([]);
    } catch (err) { setNetworkActionMessage(err instanceof Error ? err.message : "Deal Room could not be opened."); }
  }

  async function sendDealRoomMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!dealRoom || !dealDraft.trim()) return;
    try {
      await networkRequest("/network/deal-rooms/" + dealRoom.id + "/messages", "POST", { body: dealDraft });
      setDealDraft("");
      const messages = await networkRequest("/network/deal-rooms/" + dealRoom.id + "/messages");
      setDealRoomMessages(messages as NetworkMessage[]);
    } catch (err) { setNetworkActionMessage(err instanceof Error ? err.message : "Deal Room message could not be sent."); }
  }



  async function uploadDealFile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!dealRoom || !selectedDealFile) return;
    setFileBusy(true); setFileMessage("Preparing secure upload…");
    try {
      const upload = await networkRequest("/network/deal-rooms/" + dealRoom.id + "/files/upload-url", "POST", {
        filename: selectedDealFile.name, content_type: selectedDealFile.type, size_bytes: selectedDealFile.size
      });
      const uploadForm = new FormData();
      Object.entries(upload.fields as Record<string, string>).forEach(([key, value]) => uploadForm.append(key, value));
      uploadForm.append("file", selectedDealFile);
      const sent = await fetch(upload.upload_url, { method: "POST", body: uploadForm });
      if (!sent.ok) throw new Error("The private storage upload failed. Please try again.");
      setFileMessage("Upload received. Running malware scan…");
      const completed = await networkRequest("/network/files/" + upload.file_id + "/complete", "POST") as DealFile;
      setDealFiles(current => [completed, ...current.filter(file => file.id !== completed.id)]);
      setSelectedDealFile(null);
      const picker = document.getElementById("deal-room-file-picker") as HTMLInputElement | null;
      if (picker) picker.value = "";
      setFileMessage("Document uploaded, scanned and shared securely.");
    } catch (err) { setFileMessage(err instanceof Error ? err.message : "Document upload failed."); }
    finally { setFileBusy(false); }
  }

  async function downloadDealFile(file: DealFile) {
    try {
      const result = await networkRequest("/network/files/" + file.id + "/download-url", "POST");
      window.open(result.download_url, "_blank", "noopener,noreferrer");
    } catch (err) { setFileMessage(err instanceof Error ? err.message : "Secure download could not be created."); }
  }

  async function sendQuotation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!dealRoom) return;
    try {
      const quote = await networkRequest("/network/deal-rooms/" + dealRoom.id + "/quotations", "POST", {
        title: quoteTitle, currency: quoteCurrency, valid_until: quoteValidUntil || null, notes: quoteNotes || null,
        line_items: quoteLines.map(line => ({...line, quantity: Number(line.quantity), unit_price: Number(line.unit_price), tax_rate: Number(line.tax_rate)}))
      }) as Quotation;
      setQuotations(current => [quote, ...current]);
      setQuoteTitle(""); setQuoteValidUntil(""); setQuoteNotes("");
      setQuoteLines([{description:"",quantity:"1",unit_price:"",tax_rate:"15"}]);
      setNetworkActionMessage("Quotation " + quote.reference + " shared in this Deal Room.");
    } catch (err) { setNetworkActionMessage(err instanceof Error ? err.message : "Quotation could not be shared."); }
  }

  async function decideQuotation(quotationId: string, decision: "accepted" | "declined") {
    try {
      const updated = await networkRequest("/network/quotations/" + quotationId + "/decision", "POST", {decision}) as Quotation;
      setQuotations(current => current.map(item => item.id === quotationId ? updated : item));
    } catch (err) { setNetworkActionMessage(err instanceof Error ? err.message : "Quotation response could not be saved."); }
  }

  async function updateDealStatus(status: string) {
    if (!dealRoom) return;
    try {
      const updated = await networkRequest("/network/deal-rooms/" + dealRoom.id, "PATCH", { status }) as DealRoom;
      setDealRoom(updated);
      if (selectedConversation) {
        const next = { ...selectedConversation, deal_room_status: updated.status };
        setSelectedConversation(next);
        setConversations(current => current.map(item => item.id === next.id ? next : item));
      }
    } catch (err) { setNetworkActionMessage(err instanceof Error ? err.message : "Deal status could not be updated."); }
  }

  async function submitAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const payload = mode === "register"
      ? { full_name: fullName, email, password, business_name: businessName, industry, country, profile_image_data_url: profileImage, referral_code: referralCode.trim() || null }
      : { identifier: email, password };
    try {
      const response = await fetch(`${API_BASE}/auth/${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "We couldn't complete your request. Please try again.");
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(data));
      setSession(data as AuthData);
      setProfileDraft({
        name: data.business.name, industry: data.business.industry, country: data.business.country,
        registration_number: data.business.registration_number ?? "", website: data.business.website ?? "",
        contact_email: data.business.contact_email ?? "", phone: data.business.phone ?? "",
        address_line: data.business.address_line ?? "", city: data.business.city ?? "",
        province: data.business.province ?? "", postal_code: data.business.postal_code ?? "",
        description: data.business.description ?? "", profile_image_data_url: data.business.profile_image_data_url ?? null,
        directory_listed: data.business.directory_listed ?? false, public_email: data.business.public_email ?? false,
        public_phone: data.business.public_phone ?? false, public_website: data.business.public_website ?? false,
        public_location: data.business.public_location ?? false,
      });
      setProfileImage(data.business.profile_image_data_url ?? null);
      setPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to connect. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  function updateProfileField(field: keyof BusinessProfile, value: string) {
    setProfileDraft(current => ({ ...current, [field]: value }));
  }

  async function saveBusinessProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session) return;
    setProfileBusy(true);
    setProfileMessage("");
    try {
      const response = await fetch(API_BASE + "/auth/business/profile", {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: "Bearer " + session.access_token },
        body: JSON.stringify(profileDraft),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "We couldn't save your business profile.");
      const nextSession = { ...session, business: data };
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(nextSession));
      setSession(nextSession);
      setProfileDraft(data);
      setProfileImage(data.profile_image_data_url ?? null);
      setProfileMessage("Business profile saved.");
    } catch (err) {
      setProfileMessage(err instanceof Error ? err.message : "Unable to save your profile.");
    } finally {
      setProfileBusy(false);
    }
  }

  async function searchBusinessDirectory(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (!session) return;
    setDirectoryBusy(true);
    setDirectoryMessage("");
    try {
      const params = new URLSearchParams();
      if (directoryQuery.trim()) params.set("q", directoryQuery.trim());
      const response = await fetch(API_BASE + "/network/businesses?" + params.toString(), {
        headers: { Authorization: "Bearer " + session.access_token },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Unable to load the Business Network.");
      setDirectoryResults(data as PublicBusiness[]);
      if (!data.length) setDirectoryMessage("No listed businesses found yet. Try another search or invite a business to join.");
    } catch (err) {
      setDirectoryMessage(err instanceof Error ? err.message : "Unable to load the directory.");
    } finally {
      setDirectoryBusy(false);
    }
  }

  function signOut() {
    sessionStorage.removeItem(STORAGE_KEY);
    setSession(null);
    setMode("login");
  }

  async function acceptStaffInvite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setStaffAcceptBusy(true); setStaffAcceptMessage("");
    try { const response = await fetch(API_BASE + "/staff/accept", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token: staffInviteToken, full_name: staffAcceptName, password: staffAcceptPassword }) }); const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Invitation could not be accepted."); setStaffAcceptMessage("Invitation accepted. Signing you in…"); const loginResponse = await fetch(API_BASE + "/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ identifier: data.phone, password: staffAcceptPassword }) }); const loginData = await loginResponse.json(); if (!loginResponse.ok) throw new Error(loginData.detail || "Invitation accepted. Please sign in using your WhatsApp number."); sessionStorage.setItem(STORAGE_KEY, JSON.stringify(loginData)); setSession(loginData); window.history.replaceState({}, "", "/"); }
    catch (err) { setStaffAcceptMessage(err instanceof Error ? err.message : "Invitation could not be accepted."); } finally { setStaffAcceptBusy(false); }
  }

  if (!session && staffInviteToken) return <div className="auth-page"><div className="auth-brand"><div className="brand-mark"><Activity size={22}/></div><span>VEXION</span></div><section className="auth-card"><div className="auth-card-heading"><h2>Join your business team</h2><p>Complete your staff account using your invitation.</p></div><form className="auth-form" onSubmit={acceptStaffInvite}><label>Your full name<input required minLength={2} maxLength={160} value={staffAcceptName} onChange={e=>setStaffAcceptName(e.target.value)} /></label><p className="auth-footnote">Your WhatsApp number is already linked to this secure invitation. You will use it to sign in.</p><label>Create password<input required type="password" minLength={12} maxLength={128} value={staffAcceptPassword} onChange={e=>setStaffAcceptPassword(e.target.value)} placeholder="At least 12 characters"/></label>{staffAcceptMessage && <div className="auth-warning" role="status">{staffAcceptMessage}</div>}<button className="auth-submit" type="submit" disabled={staffAcceptBusy}>{staffAcceptBusy ? "Joining team…" : "Accept invitation"} <ArrowUpRight size={16}/></button></form><div className="auth-footnote"><LockKeyhole size={14}/> This invitation link is private and expires after 48 hours.</div></section></div>;

  if (window.location.pathname === "/careers" || window.location.pathname === "/jobs") return <PublicCareers />;

  if (!session) return <div className="auth-page">
    <div className="auth-brand"><div className="brand-mark"><Activity size={22}/></div><span>VEXION</span></div>
    <div className="auth-layout">
      <section className="auth-intro">
        <div className="eyebrow">INTELLIGENCE FOR EVERY BUSINESS.</div>
        <h1>See your business<br/><span>with clarity.</span></h1>
        <p>Bring your operations, people and business intelligence together in one secure workspace.</p>
        <div className="auth-points"><div><ShieldCheck size={18}/> Built around your business data</div><div><Building2 size={18}/> One workspace for your team</div><div><Bot size={18}/> Intelligence that grows with you</div></div>
      </section>
      <section className="auth-card">
        <div className="auth-tabs"><button className={mode === "register" ? "selected" : ""} onClick={() => {setMode("register");setError("");}}>Create account</button><button className={mode === "login" ? "selected" : ""} onClick={() => {setMode("login");setError("");}}>Sign in</button></div>
        <div className="auth-card-heading"><h2>{mode === "register" ? "Create your workspace" : "Welcome back"}</h2><p>{mode === "register" ? "Start by setting up your owner account and business." : "Sign in to continue to your business workspace."}</p></div>
        <form onSubmit={submitAuth} className="auth-form">
          {mode === "register" && <><label>Full name<input required minLength={2} maxLength={160} autoComplete="name" value={fullName} onChange={e=>setFullName(e.target.value)} placeholder="Your full name"/></label></>}
          <label>{mode === "register" ? "Business email" : "Email or WhatsApp number"}<input required type={mode === "register" ? "email" : "text"} autoComplete={mode === "register" ? "email" : "username"} value={email} onChange={e=>setEmail(e.target.value)} placeholder={mode === "register" ? "you@company.com" : "Email or +27 82 123 4567"}/></label>
          <label>Password<input required type="password" minLength={mode === "register" ? 12 : 1} maxLength={128} autoComplete={mode === "register" ? "new-password" : "current-password"} value={password} onChange={e=>setPassword(e.target.value)} placeholder={mode === "register" ? "At least 12 characters" : "Your password"}/></label>
          {mode === "register" && <><label>Business name<input required minLength={2} maxLength={200} value={businessName} onChange={e=>setBusinessName(e.target.value)} placeholder="Your registered or trading name"/></label><label>Referral code (optional)<input maxLength={20} value={referralCode} onChange={e=>setReferralCode(e.target.value.toUpperCase())} placeholder="Enter a VEXION referral code"/></label><div className="profile-upload"><div className="profile-upload-preview">{profileImage ? <img src={profileImage} alt="Business profile preview"/> : <Building2 size={25}/>}</div><div className="profile-upload-copy"><strong>Business profile picture</strong><span>Add your company logo or business photo. Optional.</span><label className="profile-upload-button">{profileImage ? "Change image" : "Upload image"}<input type="file" accept="image/jpeg,image/png,image/webp" onChange={e=>handleProfileImage(e.target.files?.[0])}/></label>{imageError && <small className="profile-upload-error">{imageError}</small>}</div></div><div className="auth-two-col"><label>Industry<input required minLength={2} maxLength={120} value={industry} onChange={e=>setIndustry(e.target.value)} placeholder="e.g. Retail"/></label><label>Country<select value={country} onChange={e=>setCountry(e.target.value)}><option value="ZA">South Africa</option><option value="NG">Nigeria</option><option value="KE">Kenya</option><option value="GH">Ghana</option><option value="BW">Botswana</option><option value="ZM">Zambia</option><option value="ZW">Zimbabwe</option><option value="OT">Other</option></select></label></div></>}
          {error && <div className="auth-error" role="alert">{error}</div>}
          {apiStatus === "offline" && <div className="auth-warning">The VEXION API is not reachable yet. Check that the backend is running and try again.</div>}
          <button className="auth-submit" type="submit" disabled={busy || apiStatus !== "online"}>{busy ? "Please wait…" : mode === "register" ? "Create business workspace" : "Sign in securely"} <ArrowUpRight size={17}/></button>
        </form>
        <div className="auth-footnote"><LockKeyhole size={14}/> Your password is securely hashed. Never share it with anyone.</div><a className="careers-entry-link" href="/careers">Looking for work? Browse open vacancies <ArrowUpRight size={14}/></a>
      </section>
    </div>
    <footer className="auth-footer">VEXION © 2026 <span>BUILD THE INTELLIGENCE THAT RUNS BUSINESSES.</span></footer>
  </div>;

  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="/" aria-label="VEXION home"><div className="brand-mark"><Activity size={22}/></div><span>VEXION</span></a>
      <div className="workspace-label">WORKSPACE</div>
      <div className="workspace-switch"><span className="workspace-icon">{session.business.profile_image_data_url ? <img src={session.business.profile_image_data_url} alt="Business profile"/> : <Building2 size={17}/>}</span><span><strong>{session.business.name}</strong><small>{session.business.industry}</small></span><ChevronRight size={16}/></div>
      <nav className="navigation" aria-label="Main navigation"><a className="nav-item active" href="#overview"><LayoutDashboard size={18}/>Overview</a><a className="nav-item" href="#pos-connections"><Activity size={18}/>POS Connections</a><a className="nav-item" href="#discrepancies"><AlertTriangle size={18}/>Discrepancies</a><a className="nav-item" href="#sales-intelligence"><ChartNoAxesCombined size={18}/>Sales Intelligence</a><a className="nav-item" href="#invoices"><FileText size={18}/>Invoices</a><a className="nav-item" href="#finance"><CreditCard size={18}/>Expenses & Profit</a><a className="nav-item" href="#billing"><CreditCard size={18}/>Billing & POS Pricing</a><a className="nav-item" href="#referrals"><Users size={18}/>Refer & Earn</a><a className="nav-item" href="#customers"><Users size={18}/>Customers</a><a className="nav-item" href="#operations"><Package size={18}/>Operations</a><a className="nav-item" href="#team"><Users size={18}/>Team Management</a><a className="nav-item" href="#people"><BriefcaseBusiness size={18}/>People & HR</a><a className="nav-item" href="#business-profile"><Building2 size={18}/>Business Profile</a><a className="nav-item" href="#network"><Building2 size={18}/>Business Network</a><a className="nav-item" href="#private-conversations"><LockKeyhole size={18}/>Private Conversations</a></nav>
      <div className="sidebar-bottom"><a className="nav-item" href="#settings"><Settings2 size={18}/>Settings</a><a className="nav-item" href="#help"><CircleHelp size={18}/>Help & support</a><button className="nav-item signout-button" onClick={signOut}><LogOut size={18}/>Sign out</button><div className="security-note"><ShieldCheck size={17}/><span>Designed with business data security at its core.</span></div></div>
    </aside>
    <main className="main-content" id="overview">
      <header className="topbar"><div className="breadcrumb">Workspace <ChevronRight size={14}/> <strong>Overview</strong></div><div className="topbar-actions"><span className={`api-indicator ${apiStatus}`}><i/>{apiStatus === "online" ? "API connected" : "API offline"}</span><button className="icon-button" aria-label="Security status"><LockKeyhole size={18}/></button><div className="avatar">{session.user.full_name.split(" ").map(x=>x[0]).slice(0,2).join("").toUpperCase()}</div></div></header>
      <section className="welcome-section"><div><div className="eyebrow">INTELLIGENCE FOR EVERY BUSINESS.</div><h1>Welcome,<br/><span>{session.user.full_name.split(" ")[0]}.</span></h1><p>Your {session.business.name} workspace is ready for connected sales, financial visibility and smarter growth decisions.</p><div className="workspace-created"><ShieldCheck size={16}/> Business workspace created successfully</div></div><div className="welcome-visual" aria-hidden="true"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="brain-core"><Bot size={52} strokeWidth={1.25}/></div><div className="orbit-dot dot-one"/><div className="orbit-dot dot-two"/><div className="orbit-dot dot-three"/><div className="visual-caption">BUSINESS INTELLIGENCE</div></div></section>
      <POSConnectionsWorkspace session={session} />
      <DailyCloseWorkspace session={session} />
      <DiscrepancyWorkspace session={session} />
      <BillingWorkspace session={session} />
      <ReferralWorkspace session={session} />
      <SalesIntelligenceWorkspace session={session} />
      <InvoiceWorkspace session={session} />
      <InventoryWorkspace session={session} />
      <SupplierPurchasingWorkspace session={session} />
      <SupplierInvoiceMatchingWorkspace session={session} />
      <SupplierPayablesWorkspace session={session} />
      <FinanceWorkspace session={session} />
      <section className="profile-centre" id="business-profile">
        <div className="profile-centre-heading"><div><div className="eyebrow">BUSINESS IDENTITY</div><h2>Business Profile & Onboarding</h2><p>Complete your business details. You control what information is shared publicly later.</p></div><span className="profile-status">Editable anytime</span></div>
        <form className="business-profile-form" onSubmit={saveBusinessProfile}>
          <div className="profile-identity-row"><div className="profile-upload-preview profile-large-preview">{(profileImage ?? profileDraft.profile_image_data_url) ? <img src={(profileImage ?? profileDraft.profile_image_data_url) as string} alt="Business logo"/> : <Building2 size={28}/>}</div><div><strong>Business logo or profile picture</strong><small>JPG, PNG or WebP · maximum 2 MB</small><label className="profile-upload-button">{(profileImage ?? profileDraft.profile_image_data_url) ? "Change picture" : "Upload picture"}<input type="file" accept="image/jpeg,image/png,image/webp" onChange={e=>handleProfileImage(e.target.files?.[0])}/></label>{imageError && <small className="profile-upload-error">{imageError}</small>}</div></div>
          <div className="profile-fields-grid">
            <label>Business name<input required maxLength={200} value={profileDraft.name} onChange={e=>updateProfileField("name",e.target.value)}/></label>
            <label>Industry<input required maxLength={120} value={profileDraft.industry} onChange={e=>updateProfileField("industry",e.target.value)}/></label>
            <label>Registration number<input maxLength={100} value={profileDraft.registration_number ?? ""} onChange={e=>updateProfileField("registration_number",e.target.value)} placeholder="e.g. CIPC number"/></label>
            <label>Website<input type="url" maxLength={255} value={profileDraft.website ?? ""} onChange={e=>updateProfileField("website",e.target.value)} placeholder="https://yourbusiness.co.za"/></label>
            <label>Business email<input type="email" value={profileDraft.contact_email ?? ""} onChange={e=>updateProfileField("contact_email",e.target.value)} placeholder="info@yourbusiness.co.za"/></label>
            <label>Business phone<input type="tel" maxLength={40} value={profileDraft.phone ?? ""} onChange={e=>updateProfileField("phone",e.target.value)} placeholder="+27..."/></label>
            <label className="profile-field-wide">Street address<input maxLength={255} value={profileDraft.address_line ?? ""} onChange={e=>updateProfileField("address_line",e.target.value)}/></label>
            <label>City / Town<input maxLength={120} value={profileDraft.city ?? ""} onChange={e=>updateProfileField("city",e.target.value)}/></label>
            <label>Province / State<input maxLength={120} value={profileDraft.province ?? ""} onChange={e=>updateProfileField("province",e.target.value)}/></label>
            <label>Postal code<input maxLength={24} value={profileDraft.postal_code ?? ""} onChange={e=>updateProfileField("postal_code",e.target.value)}/></label>
            <label>Country code<input maxLength={2} value={profileDraft.country} onChange={e=>updateProfileField("country",e.target.value.toUpperCase())}/></label>
            <label className="profile-field-wide">About the business<textarea rows={4} maxLength={2000} value={profileDraft.description ?? ""} onChange={e=>updateProfileField("description",e.target.value)} placeholder="Describe what your business does, the products or services you offer, and who you serve."/></label>
          </div>
          <div className="network-visibility">
            <div><strong>Business Network visibility</strong><p>Your business is private until you turn directory listing on. You can change these settings at any time.</p></div>
            <label className="visibility-main"><input type="checkbox" checked={!!profileDraft.directory_listed} onChange={e=>setProfileDraft(current=>({...current,directory_listed:e.target.checked}))}/> Show my business in the Business Network directory</label>
            <div className="visibility-options">
              <label><input type="checkbox" checked={!!profileDraft.public_email} disabled={!profileDraft.directory_listed} onChange={e=>setProfileDraft(current=>({...current,public_email:e.target.checked}))}/> Show business email</label>
              <label><input type="checkbox" checked={!!profileDraft.public_phone} disabled={!profileDraft.directory_listed} onChange={e=>setProfileDraft(current=>({...current,public_phone:e.target.checked}))}/> Show business phone</label>
              <label><input type="checkbox" checked={!!profileDraft.public_website} disabled={!profileDraft.directory_listed} onChange={e=>setProfileDraft(current=>({...current,public_website:e.target.checked}))}/> Show website</label>
              <label><input type="checkbox" checked={!!profileDraft.public_location} disabled={!profileDraft.directory_listed} onChange={e=>setProfileDraft(current=>({...current,public_location:e.target.checked}))}/> Show city and province</label>
            </div>
          </div>
          <div className="profile-form-footer">{profileMessage && <span className={profileMessage.includes("saved") ? "profile-success" : "profile-upload-error"} role="status">{profileMessage}</span>}<button className="auth-submit profile-save" type="submit" disabled={profileBusy}>{profileBusy ? "Saving profile…" : "Save business profile & privacy"} <ArrowUpRight size={16}/></button></div>
        </form>
      </section>

      <section className="profile-centre" id="team">
        <div className="profile-centre-heading"><div><div className="eyebrow">TEAM MANAGEMENT</div><h2>Build your business team.</h2><p>Invite staff with individual accounts and control their workspace roles.</p></div><span className="profile-status">Owner controlled</span></div>
        {staffMessage && <p className="recruitment-message" role="status">{staffMessage}</p>}{staffWhatsAppUrl && <a className="auth-submit profile-save" href={staffWhatsAppUrl} target="_blank" rel="noreferrer">Open WhatsApp and send invitation <ArrowUpRight size={16}/></a>}
        <form className="business-profile-form" onSubmit={inviteStaff}><div className="profile-fields-grid">
          <label>Team member WhatsApp number<input type="tel" required value={staffPhone} onChange={e=>setStaffPhone(e.target.value)} placeholder="+27 82 123 4567"/></label>
          <label>Access role<select value={staffRole} onChange={e=>setStaffRole(e.target.value)}><option value="employee">Employee</option><option value="manager">Manager</option><option value="hr">HR</option><option value="admin">Administrator</option></select></label>
        </div><div className="profile-form-footer"><button className="auth-submit profile-save" type="submit" disabled={staffBusy}>{staffBusy ? "Sending invitation…" : "Invite staff member"} <ArrowUpRight size={16}/></button></div></form>
        <div className="network-subheading"><h3>Current team</h3><button type="button" onClick={()=>void refreshStaff()}>Refresh</button></div>
        <div className="applicant-grid">{staff.map(member=><article className="applicant-card" key={member.id}><div className="applicant-card-head"><div className="applicant-avatar">{member.full_name.split(" ").map((part:string)=>part[0]).slice(0,2).join("").toUpperCase()}</div><div className="applicant-identity"><h4>{member.full_name}</h4><span>{member.phone ? "+" + member.phone : "WhatsApp number not recorded"}</span></div><span className="applicant-status">{member.role}</span></div><div className="applicant-card-footer">{member.role!=="owner" && <><select aria-label={"Role for "+member.full_name} value={member.role} onChange={e=>changeStaffRole(member.id,e.target.value)}><option value="employee">Employee</option><option value="manager">Manager</option><option value="hr">HR</option><option value="admin">Administrator</option></select><button type="button" className="network-secondary-button" onClick={()=>removeStaff(member.id)}>Remove access</button></>}</div></article>)}</div>
        <div className="network-subheading"><h3>Pending invitations</h3><span>{staffInvitations.filter(item=>item.status==="pending").length} pending</span></div>
        <div className="directory-grid">{staffInvitations.filter(item=>item.status==="pending").map(item=><article className="directory-card" key={item.id}><h3>{item.phone}</h3><p>{item.role} · Expires {new Date(item.expires_at).toLocaleString()}</p><span className="profile-status">Invitation pending</span></article>)}</div>
      </section>
      <section className="recruitment-centre" id="people">
        <div className="profile-centre-heading"><div><div className="eyebrow">PEOPLE & RECRUITMENT</div><h2>Find the people who move business forward.</h2><p>Publish vacancies, review applicants and manage each candidate through a clear hiring pipeline.</p></div><span className="profile-status">Private to your business</span></div>
        {recruitmentMessage && <p className="recruitment-message" role="status">{recruitmentMessage}</p>}
        <div className="recruitment-stats"><article><span>Open vacancies</span><strong>{jobs.filter(job=>job.status==="published").length}</strong></article><article><span>Total applicants</span><strong>{applications.length}</strong></article><article><span>Shortlisted</span><strong>{applications.filter(app=>app.status==="shortlisted" || app.status==="interview").length}</strong></article><article><span>New applications</span><strong>{applications.filter(app=>app.status==="new").length}</strong></article></div>
        <div className="recruitment-layout">
          <form className="job-create-card" onSubmit={createJob}><div className="recruitment-card-heading"><div><span className="eyebrow">NEW OPPORTUNITY</span><h3>Publish a vacancy</h3></div><span className="profile-status">Company hiring</span></div>
            <label>Job title<input required minLength={3} maxLength={180} value={jobTitle} onChange={e=>setJobTitle(e.target.value)} placeholder="e.g. Sales Manager"/></label>
            <div className="auth-two-col"><label>Department<input value={jobDepartment} onChange={e=>setJobDepartment(e.target.value)} placeholder="e.g. Sales"/></label><label>Location<input value={jobLocation} onChange={e=>setJobLocation(e.target.value)} placeholder="e.g. Durban / Hybrid"/></label></div>
            <label>Employment type<select value={jobType} onChange={e=>setJobType(e.target.value)}><option value="full_time">Full time</option><option value="part_time">Part time</option><option value="contract">Contract</option><option value="internship">Internship</option><option value="temporary">Temporary</option></select></label>
            <label>Job description<textarea required minLength={30} maxLength={12000} rows={5} value={jobDescription} onChange={e=>setJobDescription(e.target.value)} placeholder="Describe the role, responsibilities and what success looks like."/></label>
            <label>Requirements (optional)<textarea maxLength={8000} rows={3} value={jobRequirements} onChange={e=>setJobRequirements(e.target.value)} placeholder="Skills, qualifications and experience."/></label>
            <button className="auth-submit" type="submit" disabled={recruitmentBusy}>{recruitmentBusy ? "Publishing…" : "Publish vacancy"} <ArrowUpRight size={16}/></button>
          </form>
          <div className="recruitment-jobs"><div className="recruitment-card-heading"><div><span className="eyebrow">YOUR OPEN ROLES</span><h3>Vacancies</h3></div><span className="module-count">{jobs.length} TOTAL</span></div>
            {jobs.length===0 && <p className="network-empty">No vacancies yet. Publish your first role to start building your hiring pipeline.</p>}
            {jobs.map(job=><article className="job-card" key={job.id}><div className="job-card-top"><div><h4>{job.title}</h4><span>{job.department || "General"} · {job.location || "Location not specified"} · {job.employment_type.replace("_"," ")}</span></div><span className={"job-status "+job.status}>{job.status}</span></div><p>{job.description}</p><div className="job-card-footer"><span>{job.application_count} applicants</span><select aria-label={"Change status for "+job.title} value={job.status} onChange={e=>changeJobStatus(job.id,e.target.value)}><option value="draft">Draft</option><option value="published">Published</option><option value="closed">Closed</option></select></div></article>)}
          </div>
        </div>
        <div className="applicants-panel"><div className="recruitment-card-heading"><div><span className="eyebrow">CANDIDATE PIPELINE</span><h3>Applicants</h3><p>Review candidate profiles and move each application to the next stage.</p></div><select aria-label="Filter applicants" value={applicantFilter} onChange={e=>setApplicantFilter(e.target.value)}><option value="all">All applicants</option><option value="new">New</option><option value="reviewing">Reviewing</option><option value="shortlisted">Shortlisted</option><option value="interview">Interview</option><option value="hired">Hired</option><option value="rejected">Rejected</option></select></div>
          {applications.filter(app=>applicantFilter==="all" || app.status===applicantFilter).length===0 && <p className="network-empty">Applicant cards will appear here when people apply to your published vacancies.</p>}
          <div className="applicant-grid">{applications.filter(app=>applicantFilter==="all" || app.status===applicantFilter).map(app=><article className="applicant-card" key={app.id}><div className="applicant-card-head"><div className="applicant-avatar">{app.applicant_name.split(" ").map((part:string)=>part[0]).slice(0,2).join("").toUpperCase()}</div><div className="applicant-identity"><h4>{app.applicant_name}</h4><span>{app.job_title}</span></div><span className={"applicant-status "+app.status}>{app.status}</span></div><div className="applicant-meta"><span>{app.location || "Location not supplied"}</span><span>{app.experience || "Experience not supplied"}</span><a href={"mailto:"+app.email}>{app.email}</a>{app.phone && <span>{app.phone}</span>}</div>{app.cover_letter && <p className="applicant-cover">{app.cover_letter}</p>}<div className="applicant-card-footer">{app.resume_url && <a href={app.resume_url} target="_blank" rel="noreferrer">View CV <ArrowUpRight size={13}/></a>}<select aria-label={"Update "+app.applicant_name+" application"} value={app.status} onChange={e=>changeApplicantStatus(app.id,e.target.value)}><option value="new">New</option><option value="reviewing">Reviewing</option><option value="shortlisted">Shortlisted</option><option value="interview">Interview</option><option value="rejected">Rejected</option><option value="hired">Hired</option></select></div></article>)}</div>
        </div>
      </section>
      <section className="network-centre" id="network">
        <div className="profile-centre-heading"><div><div className="eyebrow">BUSINESS NETWORK</div><h2>Discover businesses</h2><p>Find companies that have chosen to make their profiles visible to the network.</p></div><span className="profile-status">Opt-in directory</span></div>
        <form className="directory-search" onSubmit={searchBusinessDirectory}><input aria-label="Search businesses" value={directoryQuery} onChange={e=>setDirectoryQuery(e.target.value)} placeholder="Search by business, industry, service or city"/><button className="auth-submit" type="submit" disabled={directoryBusy}>{directoryBusy ? "Searching…" : "Search businesses"} <ArrowUpRight size={16}/></button></form>
        {directoryMessage && <p className="directory-message" role="status">{directoryMessage}</p>}
        <div className="directory-grid">{directoryResults.map(business=><article className="directory-card" key={business.id}>
          <div className="directory-card-head"><div className="directory-logo">{business.profile_image_data_url ? <img src={business.profile_image_data_url} alt="Business logo"/> : <Building2 size={22}/>}</div><div><h3>{business.name}</h3><span>{business.industry} · {business.country}</span></div></div>
          {business.description && <p className="directory-description">{business.description}</p>}
          {(business.city || business.province) && <p className="directory-meta">{[business.city,business.province].filter(Boolean).join(", ")}</p>}
          <div className="directory-contacts">{business.contact_email && <a href={"mailto:"+business.contact_email}>Email business</a>}{business.phone && <a href={"tel:"+business.phone}>Call business</a>}{business.website && <a href={business.website} target="_blank" rel="noreferrer">Website</a>}</div>
          <button className="network-invite-button" type="button" onClick={()=>{setInviteTarget(business);setNetworkActionMessage("");}}>Invite to private conversation</button>
        </article>)}</div>
      </section>
      {inviteTarget && <section className="network-panel invite-panel">
        <div className="profile-centre-heading"><div><div className="eyebrow">PRIVATE INVITATION</div><h2>Invite {inviteTarget.name}</h2><p>Create a password for the private conversation. Share it separately with your contact, not in this invitation.</p></div><button className="network-close" type="button" onClick={()=>setInviteTarget(null)}>Cancel</button></div>
        <form className="network-invite-form" onSubmit={sendBusinessInvitation}>
          <label>Conversation password<input required minLength={8} maxLength={128} type="password" value={invitePassword} onChange={e=>setInvitePassword(e.target.value)} placeholder="At least 8 characters"/></label>
          <label>Invitation message (optional)<textarea rows={3} maxLength={1000} value={inviteMessage} onChange={e=>setInviteMessage(e.target.value)} placeholder="Tell the business why you would like to connect."/></label>
          <button className="auth-submit" type="submit" disabled={networkActionBusy}>{networkActionBusy ? "Sending invitation…" : "Send private invitation"} <ArrowUpRight size={16}/></button>
        </form>
      </section>}
      <section className="network-panel" id="private-conversations">
        <div className="profile-centre-heading"><div><div className="eyebrow">SECURE BUSINESS COMMUNICATION</div><h2>Private conversations & Deal Rooms</h2><p>Invite another business, agree on a separate password, discuss privately and move into a Deal Room when you are ready.</p></div><span className="profile-status">Invite-only</span></div>
        {networkActionMessage && <p className="directory-message" role="status">{networkActionMessage}</p>}
        <div className="network-workspace-grid">
          <div className="network-list-column">
            <div className="network-subheading"><h3>Invitations</h3><span>{incomingInvitations.filter(item=>item.status==="pending").length} pending</span></div>
            {incomingInvitations.filter(item=>item.status==="pending").length===0 && <p className="network-empty">No pending invitations.</p>}
            {incomingInvitations.filter(item=>item.status==="pending").map(invite=><article className="invitation-card" key={invite.id}>
              <strong>{invite.host_business_name}</strong><p>{invite.invitation_message || "This business has invited you to a private conversation."}</p>
              <label>Conversation password<input type="password" minLength={8} value={acceptPassword} onChange={e=>setAcceptPassword(e.target.value)} placeholder="Enter password shared separately"/></label>
              <div className="invitation-actions"><button type="button" className="network-primary-button" disabled={networkActionBusy || acceptPassword.length<8} onClick={()=>acceptBusinessInvitation(invite.id)}>Accept</button><button type="button" className="network-secondary-button" disabled={networkActionBusy} onClick={()=>rejectBusinessInvitation(invite.id)}>Reject</button></div>
            </article>)}
            <div className="network-subheading conversation-list-heading"><h3>Conversations</h3><button type="button" onClick={()=>void refreshNetwork()}>Refresh</button></div>
            {conversations.length===0 && <p className="network-empty">Accepted private conversations will appear here.</p>}
            {conversations.map(chat=><button type="button" className={"conversation-select "+(selectedConversation?.id===chat.id?"selected":"")} key={chat.id} onClick={()=>setSelectedConversation(chat)}>
              <strong>{chat.host_business_id===session.business.id?chat.invited_business_name:chat.host_business_name}</strong>
              <span>{chat.deal_room_id ? "Deal Room · "+(chat.deal_room_status || "discussion").replaceAll("_"," ") : "Private conversation"}</span>
            </button>)}
          </div>
          <div className="network-chat-column">
            {!selectedConversation ? <div className="network-empty-state"><LockKeyhole size={30}/><strong>Your private workspace</strong><p>Select an accepted conversation to start messaging. Either business can open the Deal Room.</p></div> : <>
              <div className="chat-heading"><div><strong>{selectedConversation.host_business_id===session.business.id?selectedConversation.invited_business_name:selectedConversation.host_business_name}</strong><span>Private business conversation</span></div>{!selectedConversation.deal_room_id && <button type="button" className="network-primary-button" onClick={openDealRoom}>Open Deal Room</button>}</div>
              <div className="message-list">{conversationMessages.map(message=><article className={"message-bubble "+(message.sender_business_id===session.business.id?"own":"")} key={message.id}><strong>{message.sender_business_name} · {message.sender_user_name}</strong><p>{message.body}</p><time>{new Date(message.created_at).toLocaleString()}</time></article>)}{conversationMessages.length===0 && <p className="network-empty">No messages yet. Start the conversation.</p>}</div>
              <form className="message-compose" onSubmit={sendConversationMessage}><input value={conversationDraft} onChange={e=>setConversationDraft(e.target.value)} maxLength={5000} placeholder="Write a private message…" required/><button type="submit" disabled={!conversationDraft.trim()}>Send</button></form>
              {dealRoom && <div className="deal-room-panel">
                <div className="chat-heading"><div><strong>Deal Room</strong><span>Private negotiation space</span></div><select aria-label="Deal status" value={dealRoom.status} onChange={e=>updateDealStatus(e.target.value)}><option value="discussion">Discussion</option><option value="negotiation">Negotiation</option><option value="proposal_submitted">Proposal submitted</option><option value="agreement_reached">Agreement reached</option><option value="deal_completed">Deal completed</option><option value="deal_cancelled">Deal cancelled</option></select></div>
                <div className="message-list deal-messages">{dealRoomMessages.map(message=><article className={"message-bubble "+(message.sender_business_id===session.business.id?"own":"")} key={message.id}><strong>{message.sender_business_name}</strong><p>{message.body}</p><time>{new Date(message.created_at).toLocaleString()}</time></article>)}{dealRoomMessages.length===0 && <p className="network-empty">Use this room for proposals, commercial terms and closing discussions.</p>}</div>
                <form className="message-compose" onSubmit={sendDealRoomMessage}><input value={dealDraft} onChange={e=>setDealDraft(e.target.value)} maxLength={5000} placeholder="Write a Deal Room message…" required/><button type="submit" disabled={!dealDraft.trim()}>Send</button></form>

                <section className="deal-files-section">
                  <div className="network-subheading"><h3>Documents & attachments</h3><span>{dealFiles.length} shared files</span></div>
                  <p className="deal-files-help">Share proposals, catalogues, contracts for review and supporting documents. Files are private to these two businesses and only appear after a clean malware scan.</p>
                  <form className="deal-file-upload" onSubmit={uploadDealFile}>
                    <label className="deal-file-picker">Choose a document<input id="deal-room-file-picker" type="file" accept=".pdf,.docx,.xlsx,.pptx,.txt,.csv,.png,.jpg,.jpeg" onChange={event=>setSelectedDealFile(event.target.files?.[0] ?? null)}/></label>
                    <span className="deal-file-selected">{selectedDealFile ? selectedDealFile.name + " · " + (selectedDealFile.size/1024/1024).toFixed(2) + " MB" : "PDF, Word, Excel, PowerPoint, TXT, CSV or images · max 25 MB"}</span>
                    <button className="network-primary-button" type="submit" disabled={!selectedDealFile || fileBusy}>{fileBusy ? "Uploading securely…" : "Upload and share"}</button>
                  </form>
                  {fileMessage && <p className="deal-file-message" role="status">{fileMessage}</p>}
                  <div className="deal-file-list">{dealFiles.map(file=><article className="deal-file-card" key={file.id}><div className="deal-file-icon"><FileText size={18}/></div><div className="deal-file-info"><strong>{file.original_filename}</strong><span>Shared by {file.uploader_business_name} · {(file.size_bytes/1024/1024).toFixed(2)} MB</span></div><button type="button" className="network-secondary-button" onClick={()=>downloadDealFile(file)}>Download</button></article>)}{dealFiles.length===0 && <p className="network-empty">No scanned documents shared yet.</p>}</div>
                </section>

                <div className="quotation-section">
                  <div className="network-subheading"><h3>Shared quotations</h3><span>{quotations.length} quotations</span></div>
                  {quotations.map(quote=><article className="quotation-card" key={quote.id}>
                    <div className="quotation-card-head"><div><strong>{quote.title}</strong><small>{quote.reference} · from {quote.issuer_business_name}</small></div><span className={"quotation-status status-"+quote.status}>{quote.status.replaceAll("_"," ")}</span></div>
                    <div className="quotation-lines">{quote.line_items.map((line,index)=><div key={index}><span>{line.description} × {line.quantity}</span><strong>{quote.currency} {Number(line.line_total).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}</strong></div>)}</div>
                    <div className="quotation-totals"><span>Subtotal {quote.currency} {Number(quote.subtotal).toLocaleString(undefined,{minimumFractionDigits:2})}</span><span>Tax {quote.currency} {Number(quote.tax_total).toLocaleString(undefined,{minimumFractionDigits:2})}</span><strong>Total {quote.currency} {Number(quote.total).toLocaleString(undefined,{minimumFractionDigits:2})}</strong></div>
                    {quote.notes && <p>{quote.notes}</p>}
                    {quote.response_note && <p className="directory-meta">Response: {quote.response_note}</p>}
                    {quote.status==="sent" && quote.issuer_business_id!==session.business.id && <div className="invitation-actions"><button type="button" className="network-primary-button" onClick={()=>decideQuotation(quote.id,"accepted")}>Accept quotation</button><button type="button" className="network-secondary-button" onClick={()=>decideQuotation(quote.id,"declined")}>Decline</button></div>}
                  </article>)}
                  {quotations.length===0 && <p className="network-empty">No quotations have been shared in this Deal Room yet.</p>}
                  <form className="quotation-form" onSubmit={sendQuotation}>
                    <div className="network-subheading"><h3>Create and share a quotation</h3><span>Visible to both businesses</span></div>
                    <div className="quotation-form-grid">
                      <label>Quotation title<input required maxLength={180} value={quoteTitle} onChange={e=>setQuoteTitle(e.target.value)} placeholder="e.g. Supply of products"/></label>
                      <label>Currency<select value={quoteCurrency} onChange={e=>setQuoteCurrency(e.target.value)}><option value="ZAR">ZAR · South African rand</option><option value="USD">USD · US dollar</option><option value="EUR">EUR · Euro</option><option value="GBP">GBP · Pound sterling</option><option value="KES">KES · Kenyan shilling</option><option value="NGN">NGN · Nigerian naira</option></select></label>
                      <label>Valid until<input type="date" value={quoteValidUntil} onChange={e=>setQuoteValidUntil(e.target.value)}/></label>
                    </div>
                    <div className="quotation-line-editor">{quoteLines.map((line,index)=><div className="quotation-line-row" key={index}>
                      <input aria-label="Item description" required maxLength={240} placeholder="Item or service" value={line.description} onChange={e=>setQuoteLines(current=>current.map((item,i)=>i===index?{...item,description:e.target.value}:item))}/>
                      <input aria-label="Quantity" required type="number" min="0.001" step="0.001" placeholder="Qty" value={line.quantity} onChange={e=>setQuoteLines(current=>current.map((item,i)=>i===index?{...item,quantity:e.target.value}:item))}/>
                      <input aria-label="Unit price" required type="number" min="0" step="0.01" placeholder="Unit price" value={line.unit_price} onChange={e=>setQuoteLines(current=>current.map((item,i)=>i===index?{...item,unit_price:e.target.value}:item))}/>
                      <input aria-label="Tax rate percent" required type="number" min="0" max="100" step="0.01" placeholder="Tax %" value={line.tax_rate} onChange={e=>setQuoteLines(current=>current.map((item,i)=>i===index?{...item,tax_rate:e.target.value}:item))}/>
                      {quoteLines.length>1 && <button type="button" className="network-secondary-button" onClick={()=>setQuoteLines(current=>current.filter((_,i)=>i!==index))}>Remove</button>}
                    </div>)}</div>
                    <button type="button" className="network-secondary-button" onClick={()=>setQuoteLines(current=>[...current,{description:"",quantity:"1",unit_price:"",tax_rate:"15"}])}>+ Add line item</button>
                    <label className="quotation-notes">Notes<textarea rows={2} maxLength={3000} value={quoteNotes} onChange={e=>setQuoteNotes(e.target.value)} placeholder="Payment terms, delivery details or conditions…"/></label>
                    <button className="auth-submit quotation-submit" type="submit">Share quotation in Deal Room <ArrowUpRight size={15}/></button>
                    <p className="quotation-disclaimer">A quotation response records the business's response in VEXION. It is not a signed contract or legal acceptance of a binding agreement.</p>
                  </form>
                </div>

              </div>}
            </>}
          </div>
        </div>
      </section>
      <section className="stats-grid" aria-label="Workspace summary"><div className="stat-card"><span className="stat-icon">{session.business.profile_image_data_url ? <img src={session.business.profile_image_data_url} alt="Business profile"/> : <Building2 size={18}/>}</span><span className="stat-label">Business profile</span><strong>Created</strong><small>{session.business.country} · {session.business.industry}</small></div><div className="stat-card"><span className="stat-icon"><Users size={18}/></span><span className="stat-label">Your role</span><strong>Owner</strong><small>Workspace administrator</small></div><div className="stat-card"><span className="stat-icon"><CreditCard size={18}/></span><span className="stat-label">Financial overview</span><strong>Not connected</strong><small>Add records as you get started</small></div><div className="stat-card"><span className="stat-icon"><Activity size={18}/></span><span className="stat-label">System status</span><strong>{apiStatus === "online" ? "Connected" : "Offline"}</strong><small>Backend health check</small></div></section>
      <section className="modules-section"><div className="section-heading"><div><div className="eyebrow">THE BUSINESS OPERATING SYSTEM</div><h2>Your business, connected.</h2><p>One workspace for the work that moves your business forward.</p></div><span className="module-count">06 CORE MODULES</span></div><div className="module-grid">{modules.map(({icon: Icon,title,detail,tag}) => <article className="module-card" key={title}><div className="module-icon"><Icon size={20}/></div><span className="module-tag">{tag}</span><h3>{title}</h3><p>{detail}</p><span className="module-footer">Part of VEXION <ArrowUpRight size={14}/></span></article>)}</div></section>
      <footer className="footer"><span>VEXION © 2026</span><span>BUILD THE INTELLIGENCE THAT RUNS BUSINESSES.</span></footer>
    </main>
  </div>;
}

// Inventory stock ledger workspace is intentionally separate from POS transaction totals.
