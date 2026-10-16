/** Presentation only: identifiers remain in the source models and HTTP contracts. */
export function businessReferenceLabel(reference: { name: string; code: string }): string {
  const name = reference.name?.trim();
  const code = reference.code?.trim();
  return name && code && name !== code ? `${name} - ${code}` : name || code || 'Référence indisponible';
}
