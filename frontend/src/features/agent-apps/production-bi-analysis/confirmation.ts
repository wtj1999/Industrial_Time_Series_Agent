import type { BiConfirmField } from './types';

/** Empty lists explicitly clear optional filters. A bare {} can be treated
 * as an absent resume by the upstream BI workflow's truthiness checks. */
export function buildConfirmationResume(
  fields: readonly BiConfirmField[],
  selected: Record<string, string[]>,
): Record<string, string[]> {
  return Object.fromEntries(fields.map(field => [field.cls, [...new Set(selected[field.cls] ?? [])]]));
}
