import { useEffect, useId, useState } from "react";
import { acceptedFiles } from "./session.js";

const previewTypes = { pdf: "application/pdf", jpg: "image/jpeg", jpeg: "image/jpeg", png: "image/png" };

function Preview({ file }) {
  const [source, setSource] = useState("");
  const type = previewTypes[file.name.split(".").at(-1).toLowerCase()];
  useEffect(() => {
    if (!type) return;
    const url = URL.createObjectURL(new Blob([file], { type }));
    setSource(url);
    return () => URL.revokeObjectURL(url);
  }, [file, type]);
  if (!source) return null;
  return type === "application/pdf"
    ? <object className="file-preview" data={source} type={type} aria-label={`Vista previa de ${file.name}`}><p>El navegador no puede previsualizar este PDF.</p></object>
    : <img className="file-preview" src={source} alt={`Vista previa de ${file.name}`} />;
}

export const labExtensions = ["pdf", "csv", "jpg", "jpeg", "png"];

export default function LocalFiles({ files, onChange, label = "Seleccionar archivos", extensions = labExtensions }) {
  const id = useId();
  const [notice, setNotice] = useState("");
  const [preview, setPreview] = useState(null);
  function select(event) {
    const { clean, rejected } = acceptedFiles([...event.target.files], extensions);
    const appended = clean.filter((file) => !files.some((existing) => existing.name === file.name && existing.size === file.size && existing.lastModified === file.lastModified));
    if (appended.length) onChange([...files, ...appended]);
    setNotice(rejected ? `${rejected} archivo(s) vacío(s) o con formato no admitido.` : "");
    event.target.value = "";
  }
  return (
    <div className="local-files">
      <label htmlFor={id} className="work-button file-select">{label}</label><small>Formatos: {extensions.join(", ").toUpperCase()}</small>
      <input id={id} type="file" multiple accept={extensions.map((entry) => `.${entry}`).join(",")} onChange={select} />
      <p className="work-note" aria-live="polite">{files.length
        ? "Archivo seleccionado en esta sesión. No fue guardado en un servidor."
        : "Los archivos que selecciones estarán disponibles durante la sesión."}</p>
      {notice && <p role="alert" className="field-error">{notice}</p>}
      {files.length > 0 && <ul className="file-list">{files.map((file, index) => (
        <li key={`${file.name}-${file.lastModified}-${index}`}>
          <span><strong>{file.name}</strong><small>Disponible en sesión</small></span>
          {previewTypes[file.name.split(".").at(-1).toLowerCase()] && <button type="button" className="work-button"
            aria-pressed={preview === file} onClick={() => setPreview(preview === file ? null : file)}>{preview === file ? "Ocultar vista previa" : "Vista previa"}</button>}
          <button type="button" className="work-button" aria-label={`Quitar ${file.name}`}
            onClick={() => { onChange(files.filter((_, item) => index !== item)); if (preview === file) setPreview(null); }}>Quitar</button>
        </li>
      ))}</ul>}
      {preview && files.includes(preview) && <Preview key={`${preview.name}-${preview.lastModified}`} file={preview} />}
    </div>
  );
}

