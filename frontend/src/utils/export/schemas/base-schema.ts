/**
 * Base schema types for method-aware JSON export
 * All method-specific schemas extend these base interfaces
 */

/** Schema version for forwards compatibility */
export const SCHEMA_VERSION = "2.0";

/** Discussion method types */
export type DiscussionMethod =
  | "standard"
  | "oxford"
  | "advocate"
  | "socratic"
  | "delphi"
  | "brainstorm"
  | "tradeoff"
  | "spar";

/** Base metadata common to all methods */
export interface BaseMetadata {
  schemaVersion: string;
  exportedAt: string;
  method: DiscussionMethod;
  date: string;
  models: string[];
  question: string;
}

/** Base message in a phase */
export interface BaseMessage {
  source: string;
  role: string | null;
  content: string;
}

/** Base phase structure */
export interface BasePhase {
  number: number;
  name: string;
  messages: BaseMessage[];
}

/** Base synthesis structure */
export interface BaseSynthesis {
  synthesizer: string;
  content: string;
}

/** Base export document - all method exports extend this */
export interface BaseExportDocument {
  metadata: BaseMetadata;
  phases: BasePhase[];
  synthesis: BaseSynthesis | null;
}

/** Parsing result with optional validation warnings */
export interface ParseResult<T extends BaseExportDocument> {
  document: T;
  warnings: string[];
}

/** Confidence levels used across methods */
export type ConfidenceLevel = "HIGH" | "MEDIUM" | "LOW";

/** Confidence breakdown for synthesis */
export interface ConfidenceBreakdown {
  HIGH: number;
  MEDIUM: number;
  LOW: number;
}
