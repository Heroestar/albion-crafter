import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const AODP_BASE = "https://europe.albion-online-data.com/api/v2/stats/prices";

const CITIES = [
  "Caerleon",
  "Brecilien",
  "Bridgewatch",
  "Fort Sterling",
  "Lymhurst",
  "Martlock",
  "Thetford",
];

const SWORD_BASES = [
  "MAIN_SWORD",
  "2H_CLAYMORE",
  "2H_DUALSWORD",
  "MAIN_SCIMITAR_MORGANA",
  "2H_CLEAVER_HELL",
  "2H_DUALSCIMITAR_UNDEAD",
  "2H_CLAYMORE_AVALON",
  "MAIN_SWORD_CRYSTAL",
];

const RESOURCE_BASES = [
  "METALBAR",
  "PLANKS",
  "LEATHER",
];

const TIERS = [4, 5, 6, 7, 8];
const ENCHANTS = [0, 1, 2, 3, 4];

function buildItemIds(): string[] {
  const ids: string[] = [];
  for (const base of SWORD_BASES) {
    for (const tier of TIERS) {
      for (const enchant of ENCHANTS) {
        ids.push(enchant === 0 ? `T${tier}_${base}` : `T${tier}_${base}@${enchant}`);
      }
    }
  }
  for (const base of RESOURCE_BASES) {
    for (const tier of TIERS) {
      for (const enchant of ENCHANTS) {
        ids.push(enchant === 0 ? `T${tier}_${base}` : `T${tier}_${base}@${enchant}`);
      }
    }
  }
  return ids;
}

function extractTier(itemId: string): string {
  return itemId.split("_")[0];
}

const CITY_KEY = new Map(
  CITIES.map(c => [c.toLowerCase().replace(/\s+/g, ""), c])
);

function normalizeCity(raw: string): string {
  return CITY_KEY.get(raw.toLowerCase().replace(/\s+/g, "")) ?? raw;
}

function bestPrice(row: Record<string, unknown>): number {
  const candidates = [
    Number(row.sell_price_min ?? 0),
    Number(row.sell_price_min_quality ?? 0),
  ].filter((p) => p > 0);
  return candidates.length ? Math.min(...candidates) : 0;
}

Deno.serve(async () => {
  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  );

  const ids = buildItemIds();
  const now = new Date().toISOString();
  const toInsert: Array<{
    item_id: string;
    city: string;
    tier: string;
    price: number;
    created_at: string;
  }> = [];

  const locationsParam = encodeURIComponent(CITIES.join(","));

  for (let i = 0; i < ids.length; i += 40) {
    const chunk = ids.slice(i, i + 40);
    const url = `${AODP_BASE}/${chunk.join(",")}.json?locations=${locationsParam}&qualities=1`;

    try {
      const res = await fetch(url);
      if (!res.ok) continue;
      const rows: Record<string, unknown>[] = await res.json();

      for (const row of rows) {
        const city = normalizeCity(String(row.city ?? ""));
        if (!CITIES.includes(city)) continue;
        const price = bestPrice(row);
        if (!price) continue;
        toInsert.push({
          item_id: String(row.item_id),
          city,
          tier: extractTier(String(row.item_id)),
          price,
          created_at: now,
        });
      }
    } catch {
      // skip failing chunks, continue with rest
    }
  }

  if (toInsert.length === 0) {
    return new Response(JSON.stringify({ ok: true, inserted: 0 }), {
      headers: { "Content-Type": "application/json" },
    });
  }

  const { error } = await supabase.from("price_history").insert(toInsert);

  if (error) {
    return new Response(JSON.stringify({ ok: false, error: error.message }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  return new Response(
    JSON.stringify({ ok: true, inserted: toInsert.length }),
    { headers: { "Content-Type": "application/json" } },
  );
});
