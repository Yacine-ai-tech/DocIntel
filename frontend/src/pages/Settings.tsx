import { useState } from "react";
import { Settings2 } from "lucide-react";
import { PageHeader } from "../kit/AppShell";
import { Card } from "../kit/primitives";
import { Label, Segmented, Select } from "../kit/misc";
import { Prefs, readPrefs, savePrefs } from "../lib/api";

/* v1 "Settings" nav — real client preferences that drive the Workspace defaults. */

export default function Settings() {
  const [prefs, setPrefs] = useState<Prefs>(readPrefs());
  const set = (p: Partial<Prefs>) => { savePrefs(p); setPrefs(readPrefs()); };

  return (
    <div>
      <PageHeader title="Settings" sub="Defaults for new extractions. Stored in this browser; applied on the Workspace." />
      <Card title={<span className="flex items-center gap-2"><Settings2 size={15} /> Extraction defaults</span>}>
        <div className="grid max-w-xl gap-5">
          <div>
            <Label>Default route</Label>
            <Segmented value={prefs.route} onChange={(v) => set({ route: v })}
              options={[
                { value: "vision_premium", label: "Claude Vision" },
                { value: "vision_local", label: "Local Vision" },
                { value: "ocr_fallback", label: "OCR + LLM" },
              ]} />
          </div>
          <div>
            <Label>Default document type</Label>
            <Select value={prefs.docType} onChange={(v) => set({ docType: v })}
              options={["auto", "invoice", "receipt", "contract", "financial_report", "default"].map((v) => ({
                value: v, label: v === "auto" ? "Auto-detect" : v.replace("_", " "),
              }))} />
          </div>
          <div>
            <Label>Default result view</Label>
            <Segmented value={prefs.view} onChange={(v) => set({ view: v as Prefs["view"] })}
              options={[{ value: "cards", label: "Field cards" }, { value: "json", label: "JSON" }]} />
          </div>
        </div>
      </Card>
    </div>
  );
}
