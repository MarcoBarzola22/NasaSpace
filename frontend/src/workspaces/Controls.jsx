import { useId } from "react";

export function Field({ label, value, onChange, error, options, multiline, ...inputProps }) {
  const id = useId();
  const props = { ...inputProps, id, value: value ?? "", onChange: (event) => onChange(event.target.value),
    "aria-invalid": error ? true : undefined, "aria-describedby": error ? `${id}-error` : undefined };
  return (
    <div className="work-field">
      <label htmlFor={id}>{label}</label>
      {options ? <select {...props}><option value="">Sin dato</option>{options.map((item) => {
        const [key, text] = Array.isArray(item) ? item : [item, item];
        return <option value={key} key={key}>{text}</option>;
      })}</select> : multiline ? <textarea {...props} rows={3} /> : <input {...props} />}
      {error && <small id={`${id}-error`} className="field-error">{error}</small>}
    </div>
  );
}

export function FieldGrid({ fields, values, onChange, errors = {} }) {
  return <div className="work-fields">{fields.map(([key, label, props]) => (
    <Field key={key} label={label} value={values[key]} onChange={(value) => onChange(key, value)} error={errors[key]} {...props} />
  ))}</div>;
}

export function Panel({ title, description, children, actions }) {
  return <section className="work-panel"><div className="work-panel-heading">
    <div><h2>{title}</h2>{description && <p>{description}</p>}</div>{actions}
  </div>{children}</section>;
}

export function DataTable({ columns, rows, caption, numericColumns = [], empty = "Sin datos disponibles." }) {
  if (!rows.length) return <p className="work-empty">{empty}</p>;
  return <div className="work-table-scroll" tabIndex={0} role="region" aria-label={caption}>
    <table className="work-table"><caption>{caption}</caption><thead><tr>
      {columns.map((name, index) => <th key={name} scope="col" className={numericColumns.includes(index) ? "numeric" : undefined}>{name}</th>)}
    </tr></thead><tbody>
      {rows.map(({ id, cells, selected }) => <tr key={id} className={selected ? "work-selected" : undefined}>
        {cells.map((cell, index) => <td key={index} className={numericColumns.includes(index) ? "numeric" : undefined}>{cell === "" || cell === null || cell === undefined ? "Sin dato" : cell}</td>)}
      </tr>)}
    </tbody></table></div>;
}

export function Status({ children, tone = "neutral" }) {
  return <p className={`work-status ${tone}`}>{children}</p>;
}

