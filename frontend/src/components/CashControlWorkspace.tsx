import { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
type CashAccount = {account_label:string;currency:string;balance:string|null;balance_as_of:string;age_days:number;status:string;source:string};
type CashSummary = {
  bank_cash_balance:string|null;known_statement_balances:string|null;fresh_account_count:number;account_count:number;
  customer_receivables:string;overdue_customer_receivables:string;supplier_payables:string;overdue_supplier_payables:string;
  supplier_payables_without_due_date:string;manual_unpaid_expenses:string;manual_expenses_without_due_date:string;
  known_statement_balance_is_partial:boolean;
};
type Movement = {date:string;currency:string;expected_inflows:string;expected_outflows:string;net_scheduled_movement:string;confidence:string;items:{type:string;description:string;amount:string;direction:string;timing:string}[]};
type CashControlData = {as_of:string;horizon_days:number;horizon_end:string;cash_accounts:CashAccount[];by_currency:Record<string,CashSummary>;scheduled_movements:Movement[];data_quality:Record<string,string>};

function cashMoney(value:string|null,currency:string) {
  if(value===null)return "Unavailable";
  return new Intl.NumberFormat("en-ZA",{style:"currency",currency,minimumFractionDigits:2}).format(Number(value));
}

export default function CashControlWorkspace({session}:{session:{access_token:string}}) {
  const [data,setData]=useState<CashControlData|null>(null);
  const [horizon,setHorizon]=useState(30);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");
  async function load() {
    setLoading(true);setError("");
    try {
      const response=await fetch(API_BASE+"/cash-control/overview?horizon_days="+horizon,{headers:{Authorization:"Bearer "+session.access_token}});
      const result=await response.json();
      if(!response.ok)throw new Error(result?.detail||"Cash control could not be loaded.");
      setData(result as CashControlData);
    } catch(e) {setError(e instanceof Error?e.message:"Cash control could not be loaded.");}
    finally {setLoading(false);}
  }
  useEffect(()=>{void load();},[session.access_token,horizon]);
  const currencies=Object.keys(data?.by_currency||{});
  return <section className="finance-workspace" id="cash-control">
    <div className="finance-workspace-heading"><div><div className="eyebrow">CASH CONTROL & LIQUIDITY INTELLIGENCE</div><h2>Know where your cash stands.</h2><p>Bank statement evidence, customer money due and supplier obligations — kept separate and traceable.</p></div><div className="network-toolbar"><select aria-label="Forecast period" value={horizon} onChange={e=>setHorizon(Number(e.target.value))}><option value={7}>7-day view</option><option value={30}>30-day view</option><option value={60}>60-day view</option><option value={90}>90-day view</option></select><button type="button" className="network-secondary-button" onClick={()=>void load()}>Refresh</button></div></div>
    {error&&<div className="careers-alert" role="alert">{error}</div>}
    {loading&&!data?<p className="network-empty">Loading cash control…</p>:data&&<>
      <div className="careers-alert"><strong>Evidence first.</strong> This view does not connect to your bank in real time. A cash balance appears only when an imported statement contains a running balance. No missing balance is replaced with R0.</div>
      {currencies.length===0?<div className="network-empty">No financial records found yet. Import a bank statement with a running-balance column, issue customer invoices, or approve supplier invoices to populate this view.</div>:currencies.map(currency=>{
        const item=data.by_currency[currency];
        return <div className="finance-records" key={currency}>
          <div className="network-subheading"><h3>Liquidity overview · {currency}</h3><span>As at {data.as_of}</span></div>
          <div className="stats-grid">
            <article className="stat-card"><span className="stat-label">Latest statement cash</span><strong>{cashMoney(item.bank_cash_balance,currency)}</strong><small>{item.fresh_account_count} of {item.account_count} accounts have a balance no older than 14 days</small></article>
            <article className="stat-card"><span className="stat-label">Customer receivables</span><strong>{cashMoney(item.customer_receivables,currency)}</strong><small>{cashMoney(item.overdue_customer_receivables,currency)} overdue · not guaranteed cash</small></article>
            <article className="stat-card"><span className="stat-label">Supplier invoice payables</span><strong>{cashMoney(item.supplier_payables,currency)}</strong><small>{cashMoney(item.overdue_supplier_payables,currency)} overdue</small></article>
            <article className="stat-card"><span className="stat-label">Unpaid manual expenses</span><strong>{cashMoney(item.manual_unpaid_expenses,currency)}</strong><small>Kept separate from supplier invoice payables</small></article>
          </div>
          {item.known_statement_balance_is_partial&&<p className="directory-meta">Some accounts have missing or stale balances. The cash figure above includes only accounts with recent statement balances; it is not a complete business-wide bank balance.</p>}
          {Number(item.supplier_payables_without_due_date)>0&&<p className="directory-meta">Supplier invoices without due dates: {cashMoney(item.supplier_payables_without_due_date,currency)}. Excluded from dated forecast.</p>}
          {Number(item.manual_expenses_without_due_date)>0&&<p className="directory-meta">Manual unpaid expenses without due dates: {cashMoney(item.manual_expenses_without_due_date,currency)}. Excluded from dated forecast.</p>}
        </div>;
      })}
      <div className="finance-records"><div className="network-subheading"><h3>Scheduled cash movements</h3><span>{data.horizon_days} days · through {data.horizon_end}</span></div>
        {data.scheduled_movements.length===0?<p className="network-empty">No dated customer invoices or supplier obligations fall within this forecast window. This is not a prediction of zero cash movement.</p>:data.scheduled_movements.map((movement,index)=><article className="supplier-payable-card" key={movement.date+"-"+movement.currency+"-"+index}>
          <div className="supplier-payable-head"><div><strong>{new Date(movement.date+"T12:00:00").toLocaleDateString("en-ZA",{day:"numeric",month:"short",year:"numeric"})} · {movement.currency}</strong><small>Scheduled records only</small></div><span className="quotation-status status-pending">Estimate</span></div>
          <div className="stats-grid"><article className="stat-card"><span className="stat-label">Customer invoices due</span><strong>{cashMoney(movement.expected_inflows,movement.currency)}</strong></article><article className="stat-card"><span className="stat-label">Payments due</span><strong>{cashMoney(movement.expected_outflows,movement.currency)}</strong></article><article className="stat-card"><span className="stat-label">Scheduled net movement</span><strong>{cashMoney(movement.net_scheduled_movement,movement.currency)}</strong></article></div>
          <div className="deal-file-list">{movement.items.map((entry,i)=><div className="deal-file-card" key={i}><div className="deal-file-info"><strong>{entry.description}</strong><span>{entry.direction==="inflow"?"Customer amount due":"Obligation due"} · {entry.timing.replaceAll("_"," ")}</span></div><strong>{cashMoney(entry.amount,movement.currency)}</strong></div>)}</div>
        </article>)}
      </div>
      <div className="careers-alert"><strong>How to read this forecast</strong>{Object.entries(data.data_quality).map(([key,value])=><p key={key}><strong>{key.replaceAll("_"," ")}:</strong> {value}</p>)}</div>
      <p className="directory-meta">Statement balances older than 14 days are marked stale. Overdue and undated items are shown separately rather than assigned invented future dates. No projected sales, automatic collections, or assumed operating costs are included.</p>
    </>}
  </section>;
}
