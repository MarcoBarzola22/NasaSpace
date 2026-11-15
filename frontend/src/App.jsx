import { useEffect, useState } from "react";
import Navigation from "./components/Navigation.jsx";
import ParcelSidebar from "./components/ParcelSidebar.jsx";
import WorkspaceHeader from "./components/WorkspaceHeader.jsx";
import RotationTimeline from "./components/RotationTimeline.jsx";
import MetricsPanel from "./components/MetricsPanel.jsx";
import ContextNotes from "./components/ContextNotes.jsx";
import PrintSummary from "./components/PrintSummary.jsx";
import Inspector from "./components/Inspector.jsx";
import AssumptionsDialog from "./components/AssumptionsDialog.jsx";
import { rotations } from "./data/demo.js";

function getActiveSection() {
  return window.location.hash.slice(1) || "overview";
}

export default function App() {
  const [selectedId, setSelectedId] = useState("B");
  const [isReviewOpen, setReviewOpen] = useState(false);
  const [activeSection, setActiveSection] = useState("overview");
  const selected = rotations.find(({ id }) => id === selectedId);

  useEffect(() => {
    function syncSection() {
      setActiveSection(getActiveSection());
    }

    syncSection();
    window.addEventListener("hashchange", syncSection);
    return () => window.removeEventListener("hashchange", syncSection);
  }, []);

  const openReview = () => setReviewOpen(true);
  const closeReview = () => setReviewOpen(false);

  return (
    <>
      <div className="shell" id="overview">
        <Navigation activeSection={activeSection} />
        <ParcelSidebar onReview={openReview} />
        <main className="main">
          <WorkspaceHeader onReview={openReview} />
          <RotationTimeline rotations={rotations} selectedId={selectedId} onSelect={setSelectedId} />
          <div className="notice">
            <span aria-hidden="true" style={{ fontSize: 17, lineHeight: 1 }}>△</span>
            <span>La viabilidad de las fechas aún requiere revisión agronómica. El barbecho no implica suelo desnudo; la cobertura por rastrojos debe evaluarse por separado.</span>
          </div>
          <MetricsPanel rotations={rotations} selectedId={selectedId} />
          <ContextNotes />
          <PrintSummary rotations={rotations} />
          <footer className="footer-note">
            * Datos de interfaz totalmente ficticios. No corresponden a un lote real, no son resultados calculados con NASA POWER y no pueden utilizarse para decisiones agronómicas. AgroDSS · Prototipo visual v0.1.
          </footer>
        </main>
        <Inspector rotations={rotations} selected={selected} onSelect={setSelectedId} />
      </div>
      <AssumptionsDialog isOpen={isReviewOpen} onClose={closeReview} />
    </>
  );
}

