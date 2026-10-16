import { ReactNode } from "react";
import { GLOSSARY, GlossaryKey } from "../lib/glossary";

/** A technical term with its explanation on hover. */
export default function Term({ k, children }: { k: GlossaryKey; children?: ReactNode }) {
  return <abbr className="term" title={GLOSSARY[k]}>{children ?? k}</abbr>;
}
