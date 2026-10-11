/**
 * UniServe — shared display formatters.
 *
 * Money is stored as integer paisa throughout the API. Every PKR amount
 * rendered in the UI should go through formatPricePKR so paisa are never
 * silently dropped (previously some pages used Math.round(p / 100)).
 */

/** Format integer paisa as "PKR 1,250.00". */
export function formatPricePKR(paisa: number | null | undefined): string {
  const value = typeof paisa === "number" && Number.isFinite(paisa) ? paisa : 0;
  return `PKR ${(value / 100).toLocaleString("en-PK", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}
