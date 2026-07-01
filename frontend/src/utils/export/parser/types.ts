/**
 * Shared types and patterns for method-aware markdown parsing.
 * IMPORTANT: Patterns MUST match EXACTLY what i18n translations produce.
 */

import type { DiscussionMethod } from "../schemas/index.js";

// ============ Structural Patterns ============

/**
 * Regex patterns for identifying markdown elements.
 * Multi-language support: patterns match all 6 supported languages (EN, SV, DE, FR, ES, IT)
 */
export const STRUCTURAL_PATTERNS = {
  // Section headers (en, sv, de, fr, es, it)
  QUESTION: /^## (Question|Fråga|Frage|Question|Pregunta|Domanda)$/,
  DISCUSSION: /^## (Discussion|Diskussion|Diskussion|Discussion|Discusión|Discussione)$/,

  // Result headers - terminology.result.* (all 7 methods × 6 languages)
  RESULT: /^## (Result|Judgement|Verdict|Aporia|Aggregation|Selected Ideas|Decision|Resultat|Dom|Utslag|Apori|Aggregering|Valda idéer|Beslut|Ergebnis|Urteil|Verdikt|Aporie|Aggregation|Ausgewählte Ideen|Entscheidung|Résultat|Jugement|Verdict|Aporie|Agrégation|Idées Sélectionnées|Décision|Resultado|Juicio|Veredicto|Aporía|Agregación|Ideas Seleccionadas|Decisión|Risultato|Giudizio|Verdetto|Aporia|Aggregazione|Idee Selezionate|Decisione)$/,

  // Phase headers (en/de/fr: Phase, sv: Fas, es/it: Fase)
  PHASE: /^### (Phase|Fas|Fase) (\d+):\s*(.*)$/,

  // Message headers (all variants) - includes translated critique/position labels
  MESSAGE: /^#### (.+?)(?:\s*\[(FOR|AGAINST|ADVOCATE|DEFENDER|QUESTIONER|RESPONDENT|PANELIST|IDEATOR|EVALUATOR)\])?(?:\s*\((Critique|Final Position|Kritik|Slutposition|Kritik|Endposition|Critique|Position finale|Crítica|Posición final|Critica|Posizione finale)\))?$/,

  // Synthesis sub-headers - terminology.synthesis.* (all 7 methods × 6 languages)
  SYNTHESIS_HEADER: /^### (Synthesis|Adjudication|Ruling|Reflection|Aggregated Estimate|Final Ideas|Recommendation|Syntes|Avgörande|Beslut|Reflektion|Aggregerad uppskattning|Slutgiltiga idéer|Rekommendation|Synthese|Entscheidung|Urteil|Reflexion|Aggregierte Schätzung|Endgültige Ideen|Empfehlung|Synthèse|Jugement|Décision|Réflexion|Estimation Agrégée|Idées Finales|Recommandation|Síntesis|Adjudicación|Fallo|Reflexión|Estimación Agregada|Ideas Finales|Recomendación|Sintesi|Giudizio|Sentenza|Riflessione|Stima Aggregata|Idee Finali|Raccomandazione)$/,

  // Differences sub-headers - terminology.differences.* (all 7 methods × 6 languages)
  DIFFERENCES_HEADER: /^### (Notable Differences|Key Contentions|Unresolved Questions|Open Questions|Outlier Perspectives|Alternative Directions|Key Tradeoffs|Anmärkningsvärda skillnader|Huvudsakliga stridsfrågor|Olösta frågor|Öppna frågor|Avvikande perspektiv|Alternativa riktningar|Huvudsakliga avvägningar|Bemerkenswerte Unterschiede|Hauptstreitpunkte|Ungelöste Fragen|Offene Fragen|Abweichende Perspektiven|Alternative Richtungen|Wichtige Kompromisse|Différences Notables|Points de Contestation|Questions Non Résolues|Questions Ouvertes|Perspectives Divergentes|Directions Alternatives|Compromis Clés|Diferencias Notables|Puntos de Controversia|Preguntas Sin Resolver|Preguntas Abiertas|Perspectivas Atípicas|Direcciones Alternativas|Compensaciones Clave|Differenze Notevoli|Punti di Contesa|Domande Irrisolte|Domande Aperte|Prospettive Divergenti|Direzioni Alternative|Compromessi Chiave)$/,

  // Consensus/Decision line - terminology.consensus.* (all methods × 6 languages)
  CONSENSUS_LINE: /^\*\*(Consensus|Decision|Verdict|Aporia Reached|Convergence|Ideas Selected|Agreement|Konsensus|Beslut|Utslag|Apori nådd|Konvergens|Idéer valda|Överenskommelse|Konsens|Entscheidung|Verdikt|Aporie erreicht|Konvergenz|Ideen ausgewählt|Einigung|Consensus|Décision|Verdict|Aporie Atteinte|Convergence|Idées Sélectionnées|Accord|Consenso|Decisión|Veredicto|Aporía Alcanzada|Convergencia|Ideas Seleccionadas|Acuerdo|Consenso|Decisione|Verdetto|Aporia Raggiunta|Convergenza|Idee Selezionate|Accordo):\*\*\s*(.+)$/,

  // Synthesizer line - terminology.by.* (all methods × 6 languages)
  SYNTHESIZER_LINE: /^\*\*(Synthesized by|Adjudicated by|Ruled by|Reflected by|Aggregated by|Compiled by|Analyzed by|Syntetiserad av|Avgjord av|Beslutad av|Reflekterad av|Aggregerad av|Sammanställd av|Analyserad av|Synthetisiert von|Entschieden von|Geurteilt von|Reflektiert von|Aggregiert von|Zusammengestellt von|Analysiert von|Synthétisé par|Jugé par|Décidé par|Réfléchi par|Agrégé par|Compilé par|Analysé par|Sintetizado por|Adjudicado por|Fallado por|Reflejado por|Agregado por|Compilado por|Analizado por|Sintetizzato da|Giudicato da|Sentenziato da|Riflesso da|Aggregato da|Compilato da|Analizzato da):\*\*\s*(.+)$/,

  // Critique section markers (6 languages)
  AGREEMENTS: /^\*\*(Agreements|Överenskommelser|Übereinstimmungen|Accords|Acuerdos|Accordi):\*\*$/,
  DISAGREEMENTS: /^\*\*(Disagreements|Meningsskiljaktigheter|Meinungsverschiedenheiten|Désaccords|Desacuerdos|Disaccordi):\*\*$/,
  MISSING: /^\*\*(Missing|Saknas|Fehlend|Manquant|Faltante|Mancante):\*\*$/,

  // Position confidence (6 languages)
  CONFIDENCE: /^\*\*(Confidence|Konfidens|Konfidenz|Confiance|Confianza|Fiducia):\*\*\s*(.+)$/,

  // End markers
  SEPARATOR: /^---$/,
  FOOTER: /^\*(Exported from|Exporterad från|Exportiert von|Exporté depuis|Exportado desde|Esportato da)(?: \[Quorum\])?/,
};

// Metadata patterns (6 languages)
export const METADATA_PATTERNS = {
  DATE: /^\*\*(Date|Datum|Datum|Date|Fecha|Data):\*\*\s*(.+)$/,
  METHOD: /^\*\*(Method|Metod|Methode|Méthode|Método|Metodo):\*\*\s*(.+)$/,
  MODELS: /^\*\*(Models|Modeller|Modelle|Modèles|Modelos|Modelli):\*\*\s*(.+)$/,
};

// Multi-language message type labels
export const MESSAGE_TYPE_LABELS = {
  CRITIQUE: ["Critique", "Kritik", "Kritik", "Critique", "Crítica", "Critica"],
  POSITION: ["Final Position", "Slutposition", "Endposition", "Position finale", "Posición final", "Posizione finale"],
};

// ============ Parser Types ============

/** Role types across all methods */
export type ParsedRole =
  | "FOR"
  | "AGAINST"
  | "ADVOCATE"
  | "DEFENDER"
  | "QUESTIONER"
  | "RESPONDENT"
  | "PANELIST"
  | "IDEATOR"
  | "EVALUATOR"
  | null;

/** Raw parsed metadata before method-specific processing */
export interface RawMetadata {
  date: string;
  method: string;
  models: string[];
}

/** Validation error for method-specific constraints */
export class ParserValidationError extends Error {
  constructor(
    public methodName: string,
    public override message: string,
    public phase?: number,
    public details?: Record<string, unknown>
  ) {
    super(`[${methodName}] ${message}`);
    this.name = "ParserValidationError";
  }
}

/** Method name to DiscussionMethod mapping */
export function normalizeMethodName(method: string): DiscussionMethod {
  const normalized = method.toLowerCase().trim();
  const methodMap: Record<string, DiscussionMethod> = {
    standard: "standard",
    oxford: "oxford",
    advocate: "advocate",
    "devil's advocate": "advocate",
    socratic: "socratic",
    delphi: "delphi",
    brainstorm: "brainstorm",
    tradeoff: "tradeoff",
    spar: "spar",
  };
  return methodMap[normalized] || "standard";
}

/** Detect method from markdown content */
export function detectMethod(markdown: string): DiscussionMethod {
  // Use multiline flag to match from start of any line
  const methodPattern = new RegExp(METADATA_PATTERNS.METHOD.source, "m");
  const methodMatch = markdown.match(methodPattern);
  if (methodMatch) {
    return normalizeMethodName(methodMatch[2]);
  }
  return "standard";
}
