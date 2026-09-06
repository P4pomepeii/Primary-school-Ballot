import { comparisonProxy } from "../comparison-proxy";

export const dynamic = "force-dynamic";

export async function GET() {
  return comparisonProxy("/schools");
}
