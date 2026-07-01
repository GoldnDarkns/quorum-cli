/**
 * Parser factory and re-exports.
 * Entry point for method-aware markdown parsing.
 */

import type { BaseExportDocument, DiscussionMethod, ParseResult } from "../schemas/index.js";
import { detectMethod, ParserValidationError } from "./types.js";

// Parser imports
import { BaseParser } from "./base-parser.js";
import { StandardParser } from "./standard-parser.js";
import { OxfordParser } from "./oxford-parser.js";
import { AdvocateParser } from "./advocate-parser.js";
import { SocraticParser } from "./socratic-parser.js";
import { DelphiParser } from "./delphi-parser.js";
import { BrainstormParser } from "./brainstorm-parser.js";
import { TradeoffParser } from "./tradeoff-parser.js";

// Re-export parsers
export { BaseParser } from "./base-parser.js";
export { StandardParser } from "./standard-parser.js";
export { OxfordParser } from "./oxford-parser.js";
export { AdvocateParser } from "./advocate-parser.js";
export { SocraticParser } from "./socratic-parser.js";
export { DelphiParser } from "./delphi-parser.js";
export { BrainstormParser } from "./brainstorm-parser.js";
export { TradeoffParser } from "./tradeoff-parser.js";

// Re-export types
export { ParserValidationError, detectMethod } from "./types.js";
export type { ParsedRole } from "./types.js";
export type { ParseResult } from "../schemas/index.js";

// Re-export all schemas
export * from "../schemas/index.js";

/**
 * Parser registry mapping method names to parser classes.
 */
const PARSER_REGISTRY: Record<DiscussionMethod, new (markdown: string) => BaseParser<BaseExportDocument>> = {
  standard: StandardParser,
  oxford: OxfordParser,
  advocate: AdvocateParser,
  socratic: SocraticParser,
  delphi: DelphiParser,
  brainstorm: BrainstormParser,
  tradeoff: TradeoffParser,
  spar: StandardParser,
};

/**
 * Creates a method-specific parser based on the markdown content.
 * Automatically detects the discussion method from the markdown.
 *
 * @param markdown - The markdown content to parse
 * @returns A parser instance appropriate for the detected method
 *
 * @example
 * ```typescript
 * const parser = createParser(markdownContent);
 * const { document, warnings } = parser.parse();
 * console.log(document.metadata.method); // e.g., "oxford"
 * ```
 */
export function createParser(markdown: string): BaseParser<BaseExportDocument> {
  const method = detectMethod(markdown);
  const ParserClass = PARSER_REGISTRY[method];

  if (!ParserClass) {
    // Fallback to standard parser for unknown methods
    console.warn(`Unknown method "${method}", falling back to standard parser`);
    return new StandardParser(markdown);
  }

  return new ParserClass(markdown);
}

/**
 * Creates a parser for a specific method.
 * Use this when you know the method in advance.
 *
 * @param markdown - The markdown content to parse
 * @param method - The discussion method to use
 * @returns A parser instance for the specified method
 *
 * @example
 * ```typescript
 * const parser = createParserForMethod(markdownContent, "oxford");
 * const { document, warnings } = parser.parse();
 * ```
 */
export function createParserForMethod(
  markdown: string,
  method: DiscussionMethod
): BaseParser<BaseExportDocument> {
  const ParserClass = PARSER_REGISTRY[method];

  if (!ParserClass) {
    throw new ParserValidationError("unknown", `Unknown method: ${method}`);
  }

  return new ParserClass(markdown);
}

/**
 * Parses a markdown discussion log and returns a structured document.
 * This is the main entry point for parsing.
 *
 * @param markdown - The markdown content to parse
 * @returns Parse result with document and any warnings
 *
 * @example
 * ```typescript
 * const { document, warnings } = parseMarkdownLog(markdownContent);
 *
 * if (warnings.length > 0) {
 *   console.warn("Parse warnings:", warnings);
 * }
 *
 * // Access method-specific data
 * if (document.metadata.method === "oxford") {
 *   const oxfordDoc = document as OxfordExportDocument;
 *   console.log("Decision:", oxfordDoc.synthesis.decision);
 * }
 * ```
 */
export function parseMarkdownLog(markdown: string): ParseResult<BaseExportDocument> {
  const parser = createParser(markdown);
  return parser.parse();
}

/**
 * Parses a markdown log with a specific method parser.
 *
 * @param markdown - The markdown content to parse
 * @param method - The discussion method to use
 * @returns Parse result with document and any warnings
 */
export function parseMarkdownLogWithMethod(
  markdown: string,
  method: DiscussionMethod
): ParseResult<BaseExportDocument> {
  const parser = createParserForMethod(markdown, method);
  return parser.parse();
}

/**
 * Gets a list of all supported discussion methods.
 *
 * @returns Array of method names
 */
export function getSupportedMethods(): DiscussionMethod[] {
  return Object.keys(PARSER_REGISTRY) as DiscussionMethod[];
}

/**
 * Checks if a method is supported.
 *
 * @param method - The method name to check
 * @returns True if the method is supported
 */
export function isMethodSupported(method: string): method is DiscussionMethod {
  return method in PARSER_REGISTRY;
}
