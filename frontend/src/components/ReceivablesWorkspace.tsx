import { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
type Session = { access_token: string };
type Receipt = { id: string; amount: string; currency: string; payment_date: string; payment_method: string; reference?: string | null; verification: string };
type Receivable = {
  id: string; invoice_number: string; customer_name: string; customer_email?: string | null;
  issue_date: string; due_date: string; currency: string; status: string;
  invoice_total: string; amount_received: string; balance_due: string; days_overdue: number; payments: Receipt[];
};
type Summary = {
  as_of: string; invoice_count: number; open_invoice_count: number;
  outstanding_by_currency: Record<string,string>;
  aging_by_currency: Record<string,Record<string,string>>;
  invoices: Receivable[]; limitations: string[];
};

function money(value: string, currency: string) {
  return new Intl.NumberFormat("en-ZA", {style:"currency",currency,minimumFractionDigits:2}).format(Number(value));
}

export default function ReceivablesWorkspace({session}:{session:Session}) {
  const [data,setData]=useState<Summary|null>(null);
  const [amounts,setAmounts]=useState<Record<string,string>>({});
  const [dates,setDates]=useState<Record<string,string>>({});
  const [references,setReferences]=useState<Record<string,string>>({});
  const [methods,setMethods]=useState<Record<string,string>>({});
  const [busy,setBusy]=useState("");
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");
  const today=new Date(Date.now()-new Date().getTimezoneOffset()*60000).toISOString().slice(0,10);

  async function request(path:string,method="GET",body?:unknown) {
    const response=await fetch(API_BASE+path,{method,headers:{Authorization:"Bearer "+session.access_token,...(body?{"Content-Type":"application/json"}:{})},...(body?{body:JSON.stringify(body)}:{})});
    const result=await response.json().catch(()=>null);
    if(!response.ok)throw new Error(result?.detail||"Receivables request failed.");
    return result;
  }
  async function refresh() {
    try { setData(await request("/receivables/summary") as Summary); setError(""); }
    catch(e) { setError(e instanceof Error?e.message:"Could not load customer receivables."); }
  }
  useEffect(()=>{void refresh();},[session.access_token]);

  async function recordReceipt(invoice:Receivable) {
    const amount=amounts[invoice.id]||"";
    if(!amount||Number(amount)<=0)return;
    setBusy(invoice.id);setError("");setMessage("");
    try {
      const result=await request("/receivables/invoices/"+invoice.id+"/receipts","POST",{
        amount,payment_date:dates[invoice.id]||today,payment_method:methods[invoice.id]||"eft",
        reference:references[invoice.id]||null,idempotency_key:"vexion-customer-"+crypto.randomUUID()
      });
      setMessage("Receipt recorded for "+invoice.invoice_number+". It is marked as manually recorded, not bank-verified.");
      setAmounts(current=>({...current,[invoice.id]:""}));
      await refresh();
    } catch(e) { setError(e instanceof Error?e.message:"Could not record receipt."); }
    finally {setBusy("");}
  }

  const currencyKeys=Object.keys(data?.outstanding_by_currency||{});
  return <section className="finance-workspace" id="customer-receivables">
    <div className="finance-workspace-heading"><div><div className="eyebrow">CUSTOMER CASH COLLECTION</div><h2>Accounts receivable</h2><p>Track what customers owe, what has been received, and which invoices are overdue.</p></div><button type="button" className="network-secondary-button" onClick={()=>void refresh()}>Refresh</button></div>
    {error&&<div className="careers-alert" role="alert">{error}</div>}
    {message&&<div className="careers-alert success" role="status">{message}</div>}
    {!data?<p className="network-empty">Loading customer receivables…</p>:<>
      <div className="stats-grid">
        <article className="stat-card"><span className="stat-label">Invoices tracked</span><strong>{data.invoice_count}</strong><small>Sent, overdue and paid</small></article>
        <article className="stat-card"><span className="stat-label">Open invoices</span><strong>{data.open_invoice_count}</strong><small>With an outstanding balance</small></article>
        {currencyKeys.map(currency=><article className="stat-card" key={currency}><span className="stat-label">Outstanding · {currency}</span><strong>{money(data.outstanding_by_currency[currency],currency)}</strong><small>Customer balances still due</small></article>)}
      </div>
      {currencyKeys.map(currency=><div className="finance-records" key={currency}>
        <div className="network-subheading"><h3>Receivables ageing · {currency}</h3><span>As at {data.as_of}</span></div>
        <div className="stats-grid">
          {Object.entries(data.aging_by_currency[currency]||{}).map(([bucket,value])=><article className="stat-card" key={bucket}><span className="stat-label">{({not_due:"Not yet due", "1_30":"1–30 days overdue","31_60":"31–60 days overdue","61_plus":"61+ days overdue"} as Record<string,string>)[bucket]||bucket}</span><strong>{money(value,currency)}</strong></article>)}
        </div>
      </div>)}
      <div className="finance-records"><div className="network-subheading"><h3>Customer invoices</h3><span>{data.invoices.length} records</span></div>
        {data.invoices.length===0?<p className="network-empty">No issued customer invoices yet. Draft and cancelled invoices are excluded.</p>:data.invoices.map(invoice=><article className="supplier-payable-card" key={invoice.id}>
          <div className="supplier-payable-head"><div><strong>{invoice.customer_name}</strong><small>{invoice.invoice_number} · Due {invoice.due_date}</small></div><span className={"quotation-status status-"+invoice.status}>{invoice.status.replaceAll("_"," ")}</span></div>
          <div className="stats-grid">
            <article className="stat-card"><span className="stat-label">Invoice total</span><strong>{money(invoice.invoice_total,invoice.currency)}</strong></article>
            <article className="stat-card"><span className="stat-label">Received</span><strong>{money(invoice.amount_received,invoice.currency)}</strong></article>
            <article className="stat-card"><span className="stat-label">Balance due</span><strong>{money(invoice.balance_due,invoice.currency)}</strong></article>
          </div>
          {invoice.days_overdue>0&&<p className="directory-meta">{invoice.days_overdue} days overdue</p>}
          {invoice.payments.length>0&&<div className="deal-file-list">{invoice.payments.map(payment=><div className="deal-file-card" key={payment.id}><div className="deal-file-info"><strong>{money(payment.amount,payment.currency)} · {payment.payment_method}</strong><span>{payment.payment_date}{payment.reference?" · Ref "+payment.reference:""} · Manually recorded</span></div><span className="quotation-status status-pending">Unverified</span></div>)}</div>}
          {Number(invoice.balance_due)>0&&<form className="quotation-form" onSubmit={event=>{event.preventDefault();void recordReceipt(invoice);}}>
            <div className="network-subheading"><h3>Record customer receipt</h3><span>Balance {money(invoice.balance_due,invoice.currency)}</span></div>
            <div className="quotation-form-grid">
              <label>Amount received<input required type="number" min="0.01" max={invoice.balance_due} step="0.01" value={amounts[invoice.id]||""} onChange={e=>setAmounts(current=>({...current,[invoice.id]:e.target.value}))}/></label>
              <label>Payment date<input required type="date" value={dates[invoice.id]||today} onChange={e=>setDates(current=>({...current,[invoice.id]:e.target.value}))}/></label>
              <label>Method<select value={methods[invoice.id]||"eft"} onChange={e=>setMethods(current=>({...current,[invoice.id]:e.target.value}))}><option value="eft">EFT</option><option value="cash">Cash</option><option value="card">Card</option><option value="other">Other</option></select></label>
              <label>Reference<input maxLength={100} value={references[invoice.id]||""} onChange={e=>setReferences(current=>({...current,[invoice.id]:e.target.value}))} placeholder="Bank or receipt reference"/></label>
            </div>
            <button className="network-primary-button" type="submit" disabled={busy===invoice.id||!amounts[invoice.id]}>{busy===invoice.id?"Recording…":"Record receipt"}</button>
          </form>}
        </article>)}
      </div>
      <div className="careers-alert">{data.limitations.map(item=><p key={item}>{item}</p>)}</div>
    </>}
  </section>;
}
