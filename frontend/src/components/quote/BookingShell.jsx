import { useEffect } from "react";
import { ArrowLeft, ArrowRight, Phone } from "lucide-react";
import { Button } from "@/components/ui/button";

export function BookingShell({ prefix, eyebrow, title, steps, step, phone, aside, children }) {
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "smooth" });
    document.querySelector(`[data-testid="${prefix}-step-${step + 1}"]`)?.scrollIntoView({ inline: "center", block: "nearest" });
  }, [step, prefix]);
  return (
    <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8" data-testid={`${prefix}-page`}>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div><p className="eyebrow">{eyebrow}</p><h1 className="mt-2 text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">{title}</h1></div>
        {phone && <a href={`tel:${phone.replace(/\s/g, "")}`} className="flex items-center gap-2 text-sm font-semibold text-[#023F00]" data-testid={`${prefix}-call-link`}><Phone className="h-4 w-4" />Prefer to talk? {phone}</a>}
      </div>
      <ol className="mt-6 flex gap-1.5 overflow-x-auto pb-1" data-testid={`${prefix}-stepper`}>
        {steps.map((s, i) => (
          <li key={s} className={`whitespace-nowrap rounded-full px-3 py-1.5 font-mono text-[11px] ${i === step ? "bg-[#023F00] text-white" : i < step ? "bg-[#8F7E22]/15 text-[#023F00]" : "bg-slate-100 text-slate-500"}`} data-testid={`${prefix}-step-${i + 1}`}>{i + 1}. {s}</li>
        ))}
      </ol>
      <div className="mt-8 grid gap-10 lg:grid-cols-12">
        <section className="space-y-8 lg:col-span-7">{children}</section>
        <div className="lg:col-span-5">{aside}</div>
      </div>
    </main>
  );
}

export function StepNav({ prefix, step, last, setStep, canNext, hint, nextLabel = "Continue", onNext, children }) {
  return (
    <div className="flex flex-wrap items-center gap-3 border-t border-slate-200 pt-6">
      {step > 0 && <Button variant="ghost" onClick={() => setStep(step - 1)} data-testid={`${prefix}-back-btn`}><ArrowLeft className="mr-1 h-4 w-4" />Back</Button>}
      {step < last && <Button disabled={!canNext} onClick={() => (onNext ? onNext() : setStep(step + 1))} className="rounded-full bg-[#023F00] px-7 text-white hover:bg-[#8F7E22]" data-testid={`${prefix}-next-btn`}>{nextLabel}<ArrowRight className="ml-1 h-4 w-4" /></Button>}
      {children}
      {!canNext && hint && <span className="text-xs text-slate-500" data-testid={`${prefix}-step-hint`}>{hint}</span>}
    </div>
  );
}
