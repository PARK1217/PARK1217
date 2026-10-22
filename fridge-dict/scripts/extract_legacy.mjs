// legacy/kitchen-index.html 안의 RECIPES / SWAPS 배열을 Node vm으로 평가해 data/*.json을 만든다.
// html 문자열은 평가 결과 그대로이므로 브라우저가 보던 값과 글자 단위로 같다.
// 사용: node scripts/extract_legacy.mjs            → data/recipes.json, data/swaps.json 생성
//       node scripts/extract_legacy.mjs --check    → 기존 파일과 비교만 (다르면 exit 1)
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const LEGACY = path.join(ROOT, "legacy", "kitchen-index.html");
const OUT = { recipe: path.join(ROOT, "data", "recipes.json"), swap: path.join(ROOT, "data", "swaps.json") };

// legacy 이름 → id · 분류. 이름이 바뀌면 여기도 바꿔야 하며, 빠지면 실패한다.
const MAP = {
  recipe: {
    "스팸 김치찌개":                       ["spam-kimchi-jjigae", "가공식품"],
    "라볶이":                              ["rabokki", "면·떡"],
    "떡볶이 전골 (버섯·깻잎)":              ["tteokbokki-jeongol", "면·떡"],
    "순살 닭꼬치 구이 + 야키토리 타레":      ["chicken-skewer-yakitori-tare", "고기"],
    "지코바식 매운 양념":                   ["zikoba-spicy-sauce", "고기"],
    "사태 미역국 (뽀얀 참기름 볶음식)":      ["satae-miyeokguk", "고기"],
    "삼겹살 카레":                          ["samgyeopsal-curry", "고기"],
    "얼큰 순두부찌개":                      ["spicy-sundubu-jjigae", "두부·달걀"],
    "초당식 순두부 (양념장만)":              ["chodang-sundubu", "두부·달걀"],
    "순두부 계란찜":                        ["sundubu-gyeranjjim", "두부·달걀"],
    "뚝배기 폭탄 계란찜":                   ["ttukbaegi-gyeranjjim", "두부·달걀"],
    "전자레인지 계란찜":                    ["microwave-gyeranjjim", "두부·달걀"],
    "마가린 감자구이":                      ["margarine-potato-roast", "감자·채소"],
    "수제 감자칩":                          ["homemade-potato-chips", "감자·채소"],
    "감자고로케 그라탕":                    ["croquette-gratin", "감자·채소"],
    "부대찌개":                             ["budae-jjigae", "가공식품"],
    "쥐포 굽기":                            ["jwipo-grill", "해산물"],
    "삼치 필렛 에어프라이어":               ["samchi-fillet-airfryer", "해산물"],
    "홍게 활용":                            ["red-crab-uses", "해산물"],
    "냉동순대":                             ["frozen-sundae", "가공식품"],
    "연두부 (soft 타입)":                   ["yeondubu-soft", "두부·달걀"],
    "라면사리 활용":                        ["ramen-sari-uses", "면·떡"],
    "너비아니·산적 누린내 잡기":            ["neobiani-odor-fix", "고기"],
    "냉면육수 + 얇은 생면":                 ["naengmyeon-broth-thin-noodle", "면·떡"],
  },
  swap: {
    "새우 손질과 머리 활용":                ["shrimp-prep-heads", "손질·보관"],
    "깻잎 보관":                            ["perilla-storage", "손질·보관"],
    "너무 시어진 물김치":                   ["sour-mulkimchi", "손질·보관"],
    "청주 · 맛술 · 미림풍 조미료":          ["cheongju-mirin-guide", "재료 대체"],
    "청주가 없을 때 → 소주":                ["cheongju-to-soju", "재료 대체"],
    "버터가 없을 때 → 마가린":              ["butter-to-margarine", "재료 대체"],
    "다진 마늘 ↔ 마늘가루 ↔ 편마늘":        ["garlic-forms", "재료 대체"],
    "통후추가 없을 때 → 가루 후추":         ["whole-to-ground-pepper", "재료 대체"],
    "대파 · 양파 · 청양고추가 없을 때":     ["no-scallion-onion-chili", "재료 대체"],
    "고형 카레 ↔ 가루 카레":                ["curry-roux-vs-powder", "재료 대체"],
    "밀키트에 재료를 더할 때":              ["mealkit-additions", "도구·요령"],
    "뚝배기를 인덕션에 못 쓸 때":           ["ttukbaegi-induction", "도구·요령"],
    "큐커 · 에어프라이어 · 오븐 중 뭘 쓸까": ["cooker-airfryer-oven", "도구·요령"],
    "냉동 고기 해동과 재냉동":              ["thaw-refreeze-meat", "손질·보관"],
    "두부 · 쥐포 · 밥 보관":                ["tofu-jwipo-rice-storage", "손질·보관"],
    "사골국물은 꼭 필요한가":               ["sagol-broth-needed", "재료 대체"],
    "쌀이 모자랄 때 — 면으로 바꾸기":       ["rice-short-use-noodles", "재료 대체"],
    "껍질을 벗길까 말까":                   ["peel-or-not", "손질·보관"],
    "감자 삶는 시간":                       ["potato-boil-time", "손질·보관"],
    "불린 미역이 너무 많을 때":             ["too-much-soaked-miyeok", "손질·보관"],
    "매운 걸 못 먹는 사람과 같이 먹기":     ["eating-with-non-spicy", "도구·요령"],
  },
};

function evalArrays() {
  const src = fs.readFileSync(LEGACY, "utf8");
  const a = src.indexOf("const RECIPES = [");
  const b = src.indexOf("const TAG_ORDER");
  if (a < 0 || b < 0) throw new Error("legacy 파일에서 RECIPES/SWAPS 블록을 찾지 못함");
  const ctx = vm.createContext({});
  vm.runInContext(src.slice(a, b) + "\nglobalThis.R = RECIPES; globalThis.S = SWAPS;", ctx);
  return { recipe: ctx.R, swap: ctx.S };
}

function convert(kind, rows) {
  const map = MAP[kind];
  const seen = new Set();
  const out = rows.map((r) => {
    const m = map[r.name];
    if (!m) throw new Error(`${kind}: 매핑에 없는 이름 "${r.name}"`);
    const [id, category] = m;
    if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(id)) throw new Error(`id 형식 오류: ${id}`);
    if (seen.has(id)) throw new Error(`id 중복: ${id}`);
    seen.add(id);
    const base = { id, name: r.name, category, tags: r.tags };
    if (kind === "recipe") {
      Object.assign(base, {
        comp: r.comp || [], tools: r.tools || [], time: r.time || "",
        easy: !!r.easy, base: r.base || "",
      });
      if (r.anchor) base.anchor = { n: r.anchor.n, a: r.anchor.a, u: r.anchor.u };
    } else {
      Object.assign(base, { tools: r.tools || [], time: r.time || "" });
    }
    Object.assign(base, { added: r.added, gist: r.gist, html: r.html });
    return base;
  });
  const unused = Object.keys(map).filter((n) => !rows.some((r) => r.name === n));
  if (unused.length) throw new Error(`${kind}: legacy에 없는 매핑 ${unused.join(", ")}`);
  return out;
}

const check = process.argv.includes("--check");
const arrays = evalArrays();
let failed = false;
for (const kind of ["recipe", "swap"]) {
  const json = JSON.stringify(convert(kind, arrays[kind]), null, 2) + "\n";
  if (check) {
    const cur = fs.existsSync(OUT[kind]) ? fs.readFileSync(OUT[kind], "utf8") : "";
    if (cur !== json) { console.error(`DIFF: ${path.relative(ROOT, OUT[kind])}`); failed = true; }
    else console.log(`OK: ${path.relative(ROOT, OUT[kind])}`);
  } else {
    fs.mkdirSync(path.dirname(OUT[kind]), { recursive: true });
    fs.writeFileSync(OUT[kind], json);
    console.log(`wrote ${path.relative(ROOT, OUT[kind])} (${arrays[kind].length})`);
  }
}
if (failed) process.exit(1);
