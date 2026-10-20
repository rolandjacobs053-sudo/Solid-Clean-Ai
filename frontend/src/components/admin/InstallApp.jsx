import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const standalone = () => window.matchMedia?.("(display-mode: standalone)").matches || window.navigator.standalone;

export function InstallApp() {
  const [prompt, setPrompt] = useState(null);
  const [help, setHelp] = useState(false);
  useEffect(() => {
    const h = (e) => { e.preventDefault(); setPrompt(e); };
    window.addEventListener("beforeinstallprompt", h);
    return () => window.removeEventListener("beforeinstallprompt", h);
  }, []);
  if (standalone()) return null;
  const install = async () => {
    if (!prompt) return setHelp(true);
    prompt.prompt();
    await prompt.userChoice;
    setPrompt(null);
  };
  return (
    <>
      <Button size="sm" onClick={install} className="w-full justify-start gap-2 bg-[#8F7E22] text-white hover:bg-[#a8952b]" data-testid="install-app-btn"><Download className="h-4 w-4" />Install app</Button>
      <Dialog open={help} onOpenChange={setHelp}>
        <DialogContent data-testid="install-app-help">
          <DialogHeader><DialogTitle>Install the Solid Clean Ltd app</DialogTitle></DialogHeader>
          <div className="space-y-3 text-sm text-slate-700">
            <p><b>iPhone / iPad (Safari):</b> tap the Share button, then <b>Add to Home Screen</b>.</p>
            <p><b>Android (Chrome):</b> tap the ⋮ menu, then <b>Install app</b> or <b>Add to Home screen</b>.</p>
            <p><b>Computer (Chrome or Edge):</b> click the install icon at the right of the address bar, or the ⋮ menu → <b>Install Solid Clean Ltd</b>.</p>
            <p className="text-xs text-slate-500">The app opens straight to your dashboard with the Solid Clean Ltd icon.</p>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
