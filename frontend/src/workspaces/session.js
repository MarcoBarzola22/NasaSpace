export const emptyDraft = Object.freeze({
  identity: {}, soil: {}, studies: [], history: [], historyFiles: [], prices: [], costs: [], notes: "", strategies: [],
});

export function updateParcelDraft(drafts, parcelId, update) {
  return { ...drafts, [parcelId]: { ...(drafts[parcelId] ?? emptyDraft), ...update(drafts[parcelId] ?? emptyDraft) } };
}

export function updateRecord(records, id, patch) {
  return records.map((record) => record.id === id ? { ...record, ...patch } : record);
}

export function validateIdentity(values) {
  const errors = {};
  if (values.area && (!Number.isFinite(Number(values.area)) || Number(values.area) <= 0)) errors.area = "Ingresá una superficie mayor que cero.";
  for (const [field, bound] of [["latitude", 90], ["longitude", 180]]) {
    if (values[field] && (!Number.isFinite(Number(values[field])) || Math.abs(Number(values[field])) > bound)) errors[field] = `Ingresá un valor entre −${bound} y ${bound}.`;
  }
  for (const field of ["firstYear", "lastYear"]) {
    if (values[field] && (!/^\d{4}$/.test(values[field]) || Number(values[field]) < 1900)) errors[field] = "Ingresá un año de cuatro cifras.";
  }
  if (values.firstYear && values.lastYear && !errors.firstYear && !errors.lastYear && values.lastYear < values.firstYear) {
    errors.lastYear = "El año final debe ser posterior o igual al inicial.";
  }
  return errors;
}


export function validIdentity(values) {
  const errors = validateIdentity(values);
  return Object.fromEntries(Object.entries(values).filter(([key, value]) => !errors[key] && String(value ?? "").trim())
    .map(([key, value]) => [key, typeof value === "string" ? value.trim() : value]));
}

export function parcelWithIdentity(parcel, identity) {
  const declared = validIdentity(identity);
  const name = declared.name || (Object.hasOwn(identity, "name") ? "Nombre sin informar" : parcel.name);
  return { ...parcel, name, label: declared.name || parcel.label,
    displayId: declared.identifier || parcel.id, declared };
}

export function declaredParcelFacts(draft) {
  const identity = validIdentity(draft.identity);
  function soilValue(key) {
    const { value, unit } = draft.soil[key] ?? {};
    return value?.trim() ? [value, unit].filter(Boolean).join(" ") : "Sin informar";
  }
  return [["Superficie", identity.area ? identity.area + " ha" : "Sin informar"],
    ["Textura", soilValue("texture")], ["Profundidad efectiva", soilValue("depth")],
    ["Humedad inicial", soilValue("moisture")], ["Cultivo previo", draft.history.find(({ crop }) => crop?.trim())?.crop || "Sin informar"]];
}

export function acceptedFiles(files, extensions) {
  const clean = files.filter((file) => extensions.includes(file.name.split(".").at(-1).toLowerCase()) && file.size > 0);
  return { clean, rejected: files.length - clean.length };
}

export function studyHasResult(study) {
  return study.samples.some(({ results }) => results.some(({ value }) => value?.trim()));
}

export function studyReviewLabel(study) {
  if (!studyHasResult(study)) return "Pendiente de transcripción";
  return study.review || "Transcrito por el usuario";
}

export function exportDraft(draft) {
  const fileInfo = (file) => ({ name: file.name, size: file.size, type: file.type });
  return { ...draft, identity: validIdentity(draft.identity),
    historyFiles: draft.historyFiles.map(fileInfo),
    studies: draft.studies.map(({ files, ...study }) => ({ ...study, files: files.map(fileInfo) })),
  };
}

