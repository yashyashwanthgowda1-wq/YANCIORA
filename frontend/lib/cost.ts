/**
 * PRD §10.3:
 *   cost = input_tokens ÷ billing_unit × input_price + output_tokens ÷ billing_unit × output_price
 * Pure function. The caller always supplies the prices (user-entered today); none are built in.
 */

export interface CostInput {
  inputTokens: number;
  outputTokens: number;
  inputPrice: number; // per billing unit
  outputPrice: number; // per billing unit
  billingUnit: number; // e.g. 1_000_000 tokens
}

export interface CostBreakdown {
  inputCost: number;
  outputCost: number;
  total: number;
}

export function validateCostInput(c: CostInput): string[] {
  const errs: string[] = [];
  const fin = (n: number) => Number.isFinite(n);
  if (!fin(c.inputTokens) || c.inputTokens < 0) errs.push("Input tokens must be a number ≥ 0.");
  if (!fin(c.outputTokens) || c.outputTokens < 0) errs.push("Output tokens must be a number ≥ 0.");
  if (!fin(c.inputPrice) || c.inputPrice < 0) errs.push("Input price must be a number ≥ 0.");
  if (!fin(c.outputPrice) || c.outputPrice < 0) errs.push("Output price must be a number ≥ 0.");
  if (!fin(c.billingUnit) || c.billingUnit <= 0) errs.push("Billing unit must be greater than 0.");
  return errs;
}

export function estimateCost(c: CostInput): CostBreakdown {
  const errs = validateCostInput(c);
  if (errs.length) throw new RangeError(errs.join(" "));
  const inputCost = (c.inputTokens / c.billingUnit) * c.inputPrice;
  const outputCost = (c.outputTokens / c.billingUnit) * c.outputPrice;
  return { inputCost, outputCost, total: inputCost + outputCost };
}
